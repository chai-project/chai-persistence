# Netatmo/Efergy Persistence
The persistence package is the glue between the data collection layer, which handles the access to the APIs, and the backend API layer. The roles performed by the persistence package are threefold.

**Grouping**:
The persistence package provides a single access point to retrieve information from any home.

**Forwarding**:
Forward any request (e.g. retrieve power use, set thermostat) to the appropriate instance. 

**Polling**: Collect data for each home at reasonable intervals.

To achieve these goals the persistence package uses a singleton `Homes`. It is backed by a database containing a `homes` table. For each home this table tracks:
    
  * a unique label associated with the home;
  * a revision date; and
  * the efergy meter/netatmo relay ids.

When the information on a home changes (e.g. a meter is swapped out) it suffices to add a new row with the same unique label, updated revision date, and updated meter/relay ids. The singleton `Homes` periodically fetches the `homes` table to accommodate changes (e.g. meter swap) and additions (e.g. new home). Periodic checks are handled by a background thread. This ensures that the `Homes` instance can instantaneously respond to forwarding requests on the main thread.

To know where to look for the database and to know how to access the APIs the `Homes` singleton relies on a configuration file `settings.json`. This file is not included in the git repository for security reasons. A template of the file is included as `settings_template.json`. The format of the file is as follows:

    {
        "database": "data.db", <- location of the database
        "db_in_memory": false, <- optional; whether database is in memory
        "enable_debugging": false, <- optional; whether to show SQL queries
        "client_id": "5a339...", <- client ID of app to access Netatmo API
        "client_secret": "eQdEx..." <- client secret of app to access Netatmo API
    }

For each home the `Homes` singleton automatically logs the data. This includes the energy meter readings, and the temperature of both the thermostat and the valve. Logging happens in a separate thread for each home. Binning of energy meter readings happens in yet another thread. Information is only logged to the database when (1) information is available and (2) *all* information is available. The last condition means that binned information (*e.g.* 5 min reading) is only used when all expected bin entries are present (*e.g.* every 30 sec reading).

> **Debugging is Hard**<br>
> This package relies on fairly primitive parallelism techniques. The reasons for that are manifold but boil down to poor/disjoined support in Python for more modern async-await patterns. Basic mechanisms such as a `Thread` are notoriously hard to debug. Special care should be taken to write code that works well in any condition. *Beware that code may crash and stop with an exception in one thread, while the parent thread and other threads remain unaware*. 

> **No Failsafe**<br>
> *At the moment* there is no failsafe for missing entries. **This failsafe is nevertheless planned.** There is a two-pronged approach to implementing this failsafe. The easiest and essential part is to use the historic API endpoints of `chai-data-sources` to fill in gaps. The complimentary part is to use some form of interpolation during binning to accommodate for missing values.

Any interaction with the `Homes` singleton needs to be accompanied by a `home_label`. This value corresponds to the unique label assigned to a home in the database. The current methods are as follows.

To access the power reading of a home use `get_power(home_label: str)`.

To access the temperature in a home use `get_temperature(home_label: str, device: DeviceType)`. The `DeviceType` you specify indicates whether you want thermostat or valve information.

To change the temperature in a home use `set_device(home_label: str, device: DeviceType, temperature: int)`. Alternative calls for this method are also available that allow you to use another setpoint type or specify the minutes that the setpoint change should have effect. Once again the `DeviceType` you specify indicates whether you want thermostat or valve information. **When calling this method the setpoint change is logged *if the API reports success*.**
