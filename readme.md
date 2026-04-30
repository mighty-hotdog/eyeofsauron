# Ticket Search Bot (KTMB Shuttle Tebrau)
A continuing application that runs until terminated by error or 'ctrl C'.  
Checks for available tickets from the KTMB website "https://shuttleonline.ktmb.com.my/Home/Shuttle".  
Search parameters may be edited to modify the scope of search.  
Sends email to pre-specified alert receiver on tickets found.  

# Dev Goals
To learn python:  
1. basics - types, functions, modules, str, list, dict, array, def, class, dataclass, etc  
2. processes, subroutines, async, orchestration  
3. datetime  
4. smtp + programmatic emailing  
5. directory and file io  
6. headless website browsing/interaction with PlayWright  

# Status
Continues forever.  

Completed/runnable components:  
1. ticket_search_bot.py  
2. capture_request_ktmb.py  

Incomplete components:  
1. orchestrator_bot.py - manages bot swarm that simultaneously executes multiple ticket search requests  
2. user interface  

# Requirements
1. install:  
   1. PlayWright  
   2. orjson  
   3. Beautiful Soup  
   4. keyring  
2. setup the necessary gmail account for sending emails to work with this app  
3. setup keyring  
   1. setup backend, options: GNOME Keyring or simple encrypted file backend  
   2. add entry for alert email sending account secret  
4. copy these 2 python scripts into same directory:  
   1. capture_request_ktmb.py  
   2. ticketsearch_bot.py  

# How to run
1. run 'python3 ticket_search_bot.py' in bash  

# TODOs
1. orchestrator and user interface  
2. email addresses are hardcoded -> what's a good fix?  
3. refactor capture_request_ktmb.py  
