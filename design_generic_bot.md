# Design: generic bot

## Design Criteria
a.  runs as service or daemon on any linux node  
b.  start, run, shutdown from bash  
c.  secure + manage minimal resources for running and task execution  
d.  bot type: [name, config, attributes]  
e.  generic set of basic bot instance attributes: [eg: bot id, loop interval]  
f.  generic set of basic bot state attributes: [eg: active/idle mode, health]  
g.  generic set of basic bot type attributes: [eg: type name, feature/functionality]  
h.  generic set of basic configurable bot params  
i.  generic set of inf callable from any node: [start, shutdown, active/idle mode, reconfig, query anything, send command, health-check]  
j.  extendable with custom attributes, config params, public/controlled/internal infs, feature/functionality, logic  