# Netatmo Persistence
The persistence layer collects data continuously in the background (and should resolve any data gaps that may arise – *not implemented*). It does so for all trial homes, is aware of any updates to these homes (*e.g.* a replacement TRV), and can recover from some (but not all) failures. 

## Workings

The persistence layer runs through am ain loop that routinely inspects the database for any changes to each trial home. From within this loop (independent) child threads are spawned which individually take care of retrieving the Netatmo TRV data for their respective home and storing this data in the database.

## What Is Missing
While the persistence endpoint works well, it has some unresolved issues:

 * Due to the nature of threads it can be practically impossible to detect a failure in one thread. This does not affect other threads or the main program loop, thus almost everything looks normal. It still means that one home could not be reporting any thermostatic data. Fixing this problem is not trivial. It relies on (1) in some way validating that a thread is still active, and (2) ensuring code in a thread can never crash under any circumstance (akin to an `on error resume next` programming style).
 * Linked to the above, but not subsumed by the above, is the problem that data may be missing. Some of this data may be recoverable through alternate means from the Netatmo API and this should be implemented. When all data is missing a recovery approach should be implemented, *e.g.* by inferring values in between two data points.
