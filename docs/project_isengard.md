# Project Isengard
a user term  
an orchestrator  
a host of worker subprocs  
a jobs queue fed by constant stream of tasks  
a results queue fed by output from completed tasks  
workers poll jobs queue, remove next avail jobs to perform, return output to results queue  