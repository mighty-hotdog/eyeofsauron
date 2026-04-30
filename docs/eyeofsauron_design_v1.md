# What Application Does
- Receives user input for date(s) of interest, # of tickets, time period(s) of interest, and email address.
- Monitors ktmb webpage for available train tickets for specified parameters.
- Sends alert email when tickets available.
- Shuts down on error.
  
# How User Interacts With Application
1. User runs application which generates and displays a webpage.
2. At any time when desired, user interacts with webpage to specify/modify search/monitoring parameters:
   1. date(s) of interest
   2. number of tickets desired
   3. time period(s) of interest
   4. alert email address
3. User clicks Search button to begin looking for available tickets.
4. User watches email inbox for program's alert email.
5. At any time when desired, user clicks Stop button to stop search/monitoring.
6. At any time when desired, user clicks Quit button to exit entire application.
7. Webpage displays messages/prompts to user in the appropriate message area(s)

# Program Design
## user interface
1. python generated webpage, containing:
   1. input fields, each with its own associated message area:
      1. date of interest
      2. desired number of tickets
      3. time period of interest
      4. alert email address
   2. general message area
   3. Search button
   4. Stop button
   5. Quit button
2. application startup:
   1. checks for and reads existing "params" file
      1. if file doesn't exist, create new file with default parameters
   2. generates webpage:
      1. populates all input fields accordingly + display accompanying (error/ok) messages as appropriate
      2. sets initial status for all buttons
      3. displays welcome prompt to user
3. user interaction with webpage
   1. input field(s) change:
      1. validates input(s):
         1. displays error/ok message for invalid/valid input
         2. if all inputs are valid:
            1. updates "params" file accordingly
            2. if no existing search in progress
               1. sets Search button to active (if not alrdy) ie: user may now click and start a search
            3. if existing search in progress
               1. update parameters
   2. Search button click:
      1. validates all input fields again
      2. start new search or modify existing search with updated parameters
      3. sets Search button to inactive
      4. sets Stop button to active ie: user may click to stop search
   3. Stop button click:
      1. stop existing search
      2. sets Search button to active
      3. sets Stop button to inactive
   4. Quit button click:
      1. performs cleanup and exits application

## search bot
1. python script(s) containing search logic ie: multiple scripts each for diff targets
2. scripts have same structure and can be started/stopped/managed by cli or application
3. scripts, once started, run continuously until paused or shutdown
4. each scripts emits a heartbeat that signals their status
5. scripts allow search parameters modification without shutdown
6. each script manages its own resource pool
7. each script maintains a status profile containing information about its status

## manager process

## persistent storage
   1. "params" file containing application parameters:
      1. stored locally in same directory as application
      2. permissions???
      3. ownership???
      4. other attributes???
   2. 1st created by user interface upon any input field change