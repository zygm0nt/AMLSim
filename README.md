**Important: Please use the "master" branch for the practical use and testing. Other branches such as "new-schema" are outdated and unstable. [Wiki pages](https://github.com/IBM/AMLSim/wiki/) are still under construction and some of them do not catch up with the latest implementations. Please refer this README.md instead.**

# AMLSim
This project aims at building a multi-agent simulator of anti-money laundering - namely AML, and sharing synthetically generated data so that researchers can design and implement their new algorithms over the unified data.


# Dependencies
- Java 8 (Download and copy all jar files to `jars` directory: See also `jars/README.md`)
    - [MASON](https://cs.gmu.edu/~eclab/projects/mason/) version 18
    - [PaySim](https://github.com/EdgarLopezPhD/PaySim) (jar file already exists)
    - [Commons-Math](http://commons.apache.org/proper/commons-math/download_math.cgi) version 3.6.1
    - [JSON in Java](https://jar-download.com/artifacts/org.json/json/20180813) version 20180813
    - [WebGraph](http://webgraph.di.unimi.it/) version 3.6.1
    - [DSI Utilities](http://dsiutils.di.unimi.it/) version 2.5.4
    - [fastutil](http://fastutil.di.unimi.it/) version 8.2.3
    - [Sux for Java](http://sux.di.unimi.it/) version 4.2.0
    - [JSAP](http://www.martiansoftware.com/jsap/) version 2.1
    - [SLF4J](https://www.slf4j.org/download.html) version 1.7.25
    - [MySQL Connector for Java](https://dev.mysql.com/downloads/connector/j/5.1.html) version 5.1
- Python 3.7 (The following packages can be installed with `pip3 install -r requirements.txt`)
    - NumPy
    - networkx 1.11 (We do not support version 2.* due to performance issues for large graphs)
    - matplotlib
    - powerlaw
    - python-dateutil



# Directory Structure
See Wiki page [Directory Structure](https://github.com/IBM/AMLSim/wiki/Directory-Structure) for details.



# Introduction for Running AMLSim
See Wiki page [Quick Introduction to AMLSim](https://github.com/IBM/AMLSim/wiki/Quick-Introduction-to-AMLSim) for details.

## 1. Generate transaction CSV files from parameter files (Python)
Before running the Python script, please check and edit configuration file `conf.json`.
```json5
{
//...
  "input": {
    "directory": "paramFiles/1K",  // Parameter directory
    "schema": "schema.json",  // Configuration file of output CSV schema
    "accounts": "accounts.csv",  // Account list parameter file
    "alert_patterns": "alertPatterns.csv",  // Alert list parameter file
    "degree": "degree.csv",  // Degree sequence parameter file
    "transaction_type": "transactionType.csv",  // Transaction type list file
    "is_aggregated_accounts": true  // Whether the account list represents aggregated (true) or raw (false) accounts
  },
//...
}
```

Then, please run transaction graph generator script.
```bash
cd /path/to/AMLSim
python3 scripts/transaction_graph_generator.py conf.json
```

## 2. Build and launch the transaction simulator (Java)
Parameters for the simulator are defined at the "general" section of `conf.json`. 

```json5
{
  "general": {
      "random_seed": 0,  // Seed of random number
      "simulation_name": "sample",  // Simulation name (identifier)
      "total_steps": 720,  // Total simulation steps
      "base_date": "2017-01-01"  // The date corresponds to the step 0 (the beginning date of this simulation)
  },
//...
}
```

Please compile Java files (if not yet) and launch the simulator.
```bash
sh scripts/build_AMLSim.sh
sh scripts/run_AMLSim.sh conf.json
```


## 3. Convert the raw transaction log file
The file names of the output data are defined at the "output" section of `conf.json`.
```json5
{
//...
"output": {
    "directory": "outputs",  // Output directory
    "accounts": "accounts.csv",  // Account list CSV
    "transactions": "transactions.csv",  // All transaction list CSV
    "cash_transactions": "cash_tx.csv",  // Cash transaction list CSV
    "alert_members": "alert_accounts.csv",  // Alerted account list CSV
    "alert_transactions": "alert_transactions.csv",  // Alerted transaction list CSV
    "frauds": "frauds.csv",    // Fraud account list CSV
    "party_individuals": "individuals-bulkload.csv",
    "party_organizations": "organizations-bulkload.csv",
    "account_mapping": "accountMapping.csv",
    "resolved_entities": "resolvedentities.csv",
    "transaction_log": "tx_log.csv",
    "counter_log": "tx_count.csv",
    "diameter_log": "diameter.csv"
  },
//...
}
```

```bash
python3 scripts/convert_logs.py conf.json
```



## Remove all log and generated image files from `outputs` directory
```bash
sh scripts/clean_logs.sh
```


