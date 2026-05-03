# Dev Plan
## TODOs
1. orchestrator  
2. user interface  
3. **real** tests  
4. docker + vm distributable  
5. implement another bot type eg: air tickets, hotels/AirBnBs  

## Schedule
03 - 08 May: bots, bots pool, bots manager  
    03 May:  
    a.  generic bot + bots pool + jobs manager design criteria  
    b.  generic bot + bots pool + jobs manager design  
    04 May:  
    c.  generic bot start, run, shutdown from bash  
    d.  generic bot public API + internals  
    e.  mock orchestrator interface + internals  
    f.  mock orchestrator start, run, shutdown from bash  
    g.  generic bot public API test: start, shutdown, query, command, health-check from mock orchestrator  
    05 May:  
    h.  bots pool start, run, shutdown from bash  
    i.  bots pool public API  
    j.  bots pool internals  
    k.  bots pool public API test: start, shutdown, query, command, health-check from mock orchestrator  
    06 May:  
    l.  bots pool - generic bots integration test: with mock orchestrator  
    07 May:  
    m.  jobs_manager loop logic  
    n.  bots pool - generic bots - jobs manager integration test: with mock orchestrator  
    08 May:  
    o.  orchestrator implementation + test  
    p.  bots pool - generic bots - jobs manager integration test: with orchestrator  
09 - 11 May: requests queue  
    a.  requests queue start, run, shutdown from bash  
    b.  requests queue public API  
    c.  requests queue internals  
    d.  mock user bot interface + internals  
    e.  mock user bots start, run, shutdown from bash  
    f.  mock orchestrator start, run, shutdown from bash  
    g.  requests queue public API test: receive requests from mock user bots  
    h.  requests queue public API test: start, shutdown, query, command, health-check from mock orchestrator  
    i.  orchestrator-requests queue integration + test  
12 - 14 May: jobs queue  
    a.  jobs queue start, run, shutdown from bash  
    b.  jobs queue public API  
    c.  jobs queue internals  
    d.  mock job bot interface + internals  
    e.  mock job bots start, run, shutdown from bash  
    f.  jobs queue public API test: interacting with mock job bots  
    g.  jobs queue public API test: start, shutdown, query, command, health-check from mock orchestrator  
    h.  orchestrator-jobs queue integration + test  
    i.  requests_to_jobs loop  
15 May: config repo + bots repo  
    a.  repo start, run, shutdown from bash  
    b.  data source  
    c.  repo refresh from data source  
    d.  config repo public API + internals
    e.  mock config repo consumber bot interface + internals  
    f.  mock config repo consumer bots start, run, shutdown from bash  
    g.  config repo public API test  
    h.  bots repo public API + internals  
    i.  mock bots repo consumer bot interface + internals  
    j.  mock bots repo consumer bots start, run, shutdown from bash  
    k.  bots repo public API test  
    l.  orchestrator-config repo integration + test  
    m.  orchestrator-bots repo integration + test  