import asyncio
import logging
import signal
import sys
from dataclasses import dataclass
from typing import List, Dict, Optional
import aiohttp  # pip install aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ProcessConfig:
    name: str
    cmd: List[str]
    restart: bool = True
    max_restarts: int = 5
    backoff_base: float = 2.0

    # === New: Health check settings ===
    health_url: Optional[str] = None          # e.g. "http://127.0.0.1:8000/health"
    health_interval: float = 30.0             # seconds between checks
    health_timeout: float = 5.0               # timeout per check
    max_consecutive_failures: int = 3         # restart after this many failed checks in a row


class SubprocessOrchestrator:
    def __init__(self, configs: List[ProcessConfig]):
        self.configs = {cfg.name: cfg for cfg in configs}
        self.processes: Dict[str, asyncio.subprocess.Process] = {}
        self.restart_counts: Dict[str, int] = {}
        self.failure_counts: Dict[str, int] = {}      # for health checks
        self.running = True
        self._tasks: List[asyncio.Task] = []

    async def start_all(self):
        for name, cfg in self.configs.items():
            await self._start_process(name, cfg)
        logger.info(f"Orchestrator started {len(self.configs)} processes")

    async def _start_process(self, name: str, cfg: ProcessConfig):
        try:
            proc = await asyncio.create_subprocess_exec(
                *cfg.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.processes[name] = proc
            self.restart_counts[name] = 0
            self.failure_counts[name] = 0
            logger.info(f"Started {name} (PID {proc.pid})")

            # Core monitoring tasks
            self._tasks.extend([
                asyncio.create_task(self._monitor_process(name)),
                asyncio.create_task(self._log_output(name, proc.stdout, "stdout")),
                asyncio.create_task(self._log_output(name, proc.stderr, "stderr")),
            ])

            # Health check task (only if configured)
            if cfg.health_url:
                self._tasks.append(asyncio.create_task(self._health_monitor(name)))

        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")

    async def _log_output(self, name: str, stream, prefix: str):
        if not stream:
            return
        async for line in stream:
            if line := line.decode().rstrip():
                logger.info(f"[{name}] {prefix}: {line}")

    async def _monitor_process(self, name: str):
        """Monitor process exit and handle restarts."""
        cfg = self.configs[name]
        while self.running:
            proc = self.processes.get(name)
            if proc is None:
                break

            try:
                returncode = await proc.wait()
                logger.warning(f"{name} exited with code {returncode}")

                if not self.running or not cfg.restart:
                    break

                await self._handle_restart(name, cfg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error for {name}: {e}")

    async def _health_monitor(self, name: str):
        """Periodically ping the health endpoint."""
        cfg = self.configs[name]

        # exit if not configured
        if isinstance(cfg.health_url, str) == False or isinstance(cfg.health_timeout, float) == False:
            return
        else:
            assert cfg.health_url is str
            assert cfg.health_timeout is float
            
        connector = aiohttp.TCPConnector(limit=10)

        async with aiohttp.ClientSession(connector=connector) as session:
            while self.running:
                await asyncio.sleep(cfg.health_interval)

                if name not in self.processes:
                    continue

                try:
                    async with session.get(
                        cfg.health_url,
                        timeout=cfg.health_timeout
                    ) as resp:
                        if resp.status == 200:
                            self.failure_counts[name] = 0
                            logger.debug(f"Health check passed for {name}")
                            continue
                except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                    pass  # treat any error as failure

                # Health check failed
                self.failure_counts[name] = self.failure_counts.get(name, 0) + 1
                logger.warning(f"Health check failed for {name} ({self.failure_counts[name]}/{cfg.max_consecutive_failures})")

                if self.failure_counts[name] >= cfg.max_consecutive_failures:
                    logger.error(f"{name} failed health checks consecutively → restarting")
                    await self._restart_process(name, cfg)
                    self.failure_counts[name] = 0

    async def _restart_process(self, name: str, cfg: ProcessConfig):
        """Kill current process and start a new one."""
        if name in self.processes:
            proc = self.processes[name]
            if proc.returncode is None:
                try:
                    proc.kill()  # or .terminate() for graceful
                except ProcessLookupError:
                    pass
            self.processes.pop(name, None)

        await self._start_process(name, cfg)

    async def _handle_restart(self, name: str, cfg: ProcessConfig):
        self.restart_counts[name] = self.restart_counts.get(name, 0) + 1
        if self.restart_counts[name] > cfg.max_restarts:
            logger.error(f"{name} exceeded max restarts. Not restarting.")
            return

        backoff = cfg.backoff_base ** self.restart_counts[name]
        logger.info(f"Restarting {name} in {backoff:.1f}s (attempt {self.restart_counts[name]})")
        await asyncio.sleep(backoff)
        await self._start_process(name, cfg)

    async def stop_all(self, timeout: float = 10.0):
        self.running = False
        logger.info("Shutting down orchestrator...")

        for task in self._tasks:
            task.cancel()

        # Graceful termination
        for name, proc in list(self.processes.items()):
            if proc.returncode is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *(p.wait() for p in self.processes.values() if p.returncode is None),
                    return_exceptions=True
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Some processes did not exit in time — forcing kill")
            for proc in self.processes.values():
                if proc.returncode is None:
                    proc.kill()

        logger.info("All processes stopped.")

    async def run_forever(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_shutdown(s)))
            except NotImplementedError:
                pass

        await self.start_all()

        try:
            while self.running:
                await asyncio.sleep(10)
        finally:
            await self.stop_all()

    async def _handle_shutdown(self, sig):
        logger.info(f"Received {sig.name} — shutting down")
        await self.stop_all()


# ====================== EXAMPLE USAGE ======================

async def main():
    configs = [
        ProcessConfig(
            name="api-worker",
            cmd=[sys.executable, "api_worker.py"],
            health_url="http://127.0.0.1:8000/health",
            health_interval=15.0,
            max_consecutive_failures=3,
        ),
        ProcessConfig(
            name="playwright-scraper",
            cmd=[sys.executable, "scraper.py"],
            health_url="http://127.0.0.1:8001/healthz",
            health_interval=30.0,
        ),
        ProcessConfig(
            name="background-job",
            cmd=[sys.executable, "job_processor.py"],
            restart=True,
            # No health check → relies only on process exit monitoring
        ),
    ]

    orchestrator = SubprocessOrchestrator(configs)
    await orchestrator.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")