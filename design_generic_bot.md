# Design: generic bot

## Design Criteria
a.  runs as service or daemon  
b.  runs on any linux node anywhere network-reachable  
c.  runs in stealth  
d.  managable  
e.  start, run, shutdown from bash  
f.  secures + manages minimal resources for running and task execution  
g.  bot type: [name, config, attributes]  
h.  generic set of basic bot instance attributes:  
        [identity eg: bot id], [ops eg: loop interval], [comms method], [host related], [access level], [available functionality]  
i.  generic set of basic bot state attributes: [eg: active/idle mode, health]  
j.  generic set of basic bot type attributes: [eg: type name, feature/functionality]  
k.  generic set of basic configurable bot params  
l.  generic set of inf callable from any node: [start, shutdown, active/idle mode, reconfig, query anything, send command, health-check]  
m.  extendable with custom attributes, config params, public/controlled/internal infs, feature/functionality, logic  