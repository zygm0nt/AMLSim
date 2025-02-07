import networkx as nx
import numpy as np
import itertools
import random
import csv
import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Utility functions parsing values
def parse_int(value):
    """ Convert string to int
    :param value: string value
    :return: int value if the parameter can be converted to str, otherwise None
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_amount(value):
    """ Convert string to amount (float)
    :param value: string value
    :return: float value if the parameter can be converted to float, otherwise None
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_flag(value):
    """ Convert string to boolean (True or false)
    :param value: string value
    :return: True if the value is equal to "true" (case insensitive), otherwise False
    """
    return type(value) == str and value.lower() == "true"


class InputSchema:

    def __init__(self, input_json):
        with open(input_json, "r") as rf:
            self.data = json.load(rf)

    def get_header(self, table_name):
        fields = self.data[table_name]
        return [f["name"] for f in fields]


class TransactionGenerator:

    def __init__(self, conf_file):
        """Initialize transaction network from parameter files.
        :param conf_file: JSON file as configurations
        """
        self.g = nx.MultiDiGraph()  # Transaction graph object
        self.num_accounts = 0  # Number of total accounts
        self.degrees = dict()  # Degree distribution
        self.hubs = list()  # Hub vertices
        self.subject_candidates = set()
        self.attr_names = list()  # Additional account attribute names

        with open(conf_file, "r") as rf:
            self.conf = json.load(rf)

        general_conf = self.conf["general"]

        # Set random seed
        seed = general_conf.get("random_seed")
        self.seed = seed if seed is None else int(seed)
        np.random.seed(self.seed)
        random.seed(self.seed)

        self.total_steps = parse_int(general_conf["total_steps"])

        # Set default amounts, steps and model ID
        default_conf = self.conf["default"]
        self.default_min_amount = parse_amount(default_conf.get("min_amount"))
        self.default_max_amount = parse_amount(default_conf.get("max_amount"))
        self.default_min_balance = parse_amount(default_conf.get("min_balance"))
        self.default_max_balance = parse_amount(default_conf.get("max_balance"))
        self.default_start_step = parse_int(default_conf.get("start_step"))
        self.default_end_step = parse_int(default_conf.get("end_step"))
        self.default_start_range = parse_int(default_conf.get("start_range"))
        self.default_end_range = parse_int(default_conf.get("end_range"))
        self.default_model = parse_int(default_conf.get("transaction_model"))

        # Get input file names and properties
        input_conf = self.conf["input"]
        self.input_dir = input_conf["directory"]  # Directory name of input files
        self.account_file = input_conf["accounts"]  # Account list file
        self.alert_file = input_conf["alert_patterns"]
        self.degree_file = input_conf["degree"]
        self.type_file = input_conf["transaction_type"]
        self.is_aggregated = input_conf["is_aggregated_accounts"]

        # Get output file names
        output_conf = self.conf["temporal"]  # The destination directory is temporal
        self.output_dir = output_conf["directory"]
        self.out_tx_file = output_conf["transactions"]
        self.out_account_file = output_conf["accounts"]
        self.out_alert_file = output_conf["alert_members"]

        # Other properties for the transaction graph generator
        other_conf = self.conf["graph_generator"]
        self.degree_threshold = parse_int(other_conf["degree_threshold"])
        highrisk_countries_str = other_conf.get("high_risk_countries", "")
        highrisk_business_str = other_conf.get("high_risk_business", "")
        self.highrisk_countries = set(highrisk_countries_str.split(","))
        self.highrisk_business = set(highrisk_business_str.split(","))

        self.tx_id = 0  # Transaction ID
        self.alert_id = 0  # Alert ID from the alert parameter file
        self.alert_groups = dict()  # Alert ID and alert transaction subgraph
        self.alert_types = {"fan_out": 1, "fan_in": 2, "cycle": 3, "bipartite": 4, "stack": 5,
                            "dense": 6}  # Pattern name and model ID

        def get_types(type_csv):
            tx_types = list()
            with open(type_csv, "r") as _rf:
                reader = csv.reader(_rf)
                next(reader)
                for row in reader:
                    if row[0].startswith("#"):
                        continue
                    ttype = row[0]
                    tx_types.extend([ttype] * int(row[1]))
            return tx_types

        self.tx_types = get_types(os.path.join(self.input_dir, self.type_file))

    def set_subject_candidates(self):
        """Choose fraud subject candidates
        Currently, it chooses hub accounts with large degree
        TODO: More options how to choose fraud accounts
        """
        self.degrees = self.g.degree(self.g.nodes())
        self.hubs = [n for n in self.g.nodes() if self.degree_threshold <= self.degrees[n]]
        self.subject_candidates = set(self.g.nodes())

    # Highrisk country and business
    def is_highrisk_country(self, country):
        return country in self.highrisk_countries

    def is_highrisk_business(self, business):
        return business in self.highrisk_business

    # Account existence check
    def check_account_exist(self, aid):
        if not self.g.has_node(aid):
            raise KeyError("Account %s does not exist" % str(aid))

    def check_account_absent(self, aid):
        if self.g.has_node(aid):
            print("Warning: account %s already exists" % str(aid))
            return False
        else:
            return True

    def get_alert_members(self, num, has_subject):
        """Get account vertices randomly (high-degree vertices are likely selected)
        :param num: Number of total account vertices
        :param has_subject: Whether it has a subject account
        :return: Account ID list
        """
        found = False
        subject = None
        members = list()

        while not found:
            candidates = set()
            while len(candidates) < num:  # Get sufficient alert members
                hub = random.choice(self.hubs)
                candidates.update([hub] + list(self.g.adj[hub].keys()))
            members = np.random.choice(list(candidates), num, False)
            candidates_set = set(members) & self.subject_candidates
            if not candidates_set:
                continue
            subject = random.choice(list(candidates_set))  # Choose the subject accounts from members randomly
            found = True
            if has_subject:
                self.subject_candidates.remove(subject)
        return subject, members

    def get_account_vertices(self, num, suspicious=None):
        """Get account vertices randomly
        :param num: Number of total account vertices
        :param suspicious: If True, extract only suspicious accounts. If False, extract only non-suspicious accounts.
        If None (default), extract them from all accounts.
        :return: Account ID list
        """
        if suspicious is None:
            candidates = self.g.nodes()
        else:
            candidates = [n for n in self.g.nodes() if self.g.node[n]["suspicious"] == suspicious]  # True/False
        return random.sample(candidates, num)

    def load_account_list(self):
        """Load and add account vertices from a CSV file
        :return:
        """
        acct_file = os.path.join(self.input_dir, self.account_file)
        if self.is_aggregated:
            self.load_account_param(acct_file)
        else:
            self.load_account_raw(acct_file)

    def load_account_raw(self, acct_file):
        """Load and add account vertices from a CSV file with raw account info
        header: uuid,seq,first_name,last_name,street_addr,city,state,zip,gender,phone_number,birth_date,ssn
        :param acct_file: Account list file path
        :return:
        """
        if self.default_min_balance is None:
            raise KeyError("Option 'default_min_balance' is required to load raw account list")
        min_balance = self.default_min_balance

        if self.default_max_balance is None:
            raise KeyError("Option 'default_max_balance' is required to load raw account list")
        max_balance = self.default_max_balance

        if self.default_start_step is None or self.default_start_step < 0:
            start_day = None  # No limitation
        else:
            start_day = self.default_start_step

        if self.default_end_step is None or self.default_end_step <= 0:
            end_day = None  # No limitation
        else:
            end_day = self.default_end_step

        if self.default_start_range is None or self.default_start_range <= 0:
            start_range = None  # No limitation
        else:
            start_range = self.default_start_range

        if self.default_end_range is None or self.default_end_range <= 0:
            end_range = None  # No limitation
        else:
            end_range = self.default_end_range

        if self.default_model is None:
            default_model = 1
        else:
            default_model = self.default_model

        self.attr_names.extend(["first_name", "last_name", "street_addr", "city", "state", "zip",
                                "gender", "phone_number", "birth_date", "ssn", "lon", "lat"])

        with open(acct_file, "r") as rf:
            reader = csv.reader(rf)
            header = next(reader)
            name2idx = {n: i for i, n in enumerate(header)}
            idx_aid = name2idx["uuid"]
            idx_first_name = name2idx["first_name"]
            idx_last_name = name2idx["last_name"]
            idx_street_addr = name2idx["street_addr"]
            idx_city = name2idx["city"]
            idx_state = name2idx["state"]
            idx_zip = name2idx["zip"]
            idx_gender = name2idx["gender"]
            idx_phone_number = name2idx["phone_number"]
            idx_birth_date = name2idx["birth_date"]
            idx_ssn = name2idx["ssn"]
            idx_lon = name2idx["lon"]
            idx_lat = name2idx["lat"]

            default_country = "US"
            default_acct_type = "I"

            count = 0
            for row in reader:
                if row[0].startswith("#"):
                    continue
                aid = row[idx_aid]
                first_name = row[idx_first_name]
                last_name = row[idx_last_name]
                street_addr = row[idx_street_addr]
                city = row[idx_city]
                state = row[idx_state]
                zip_code = row[idx_zip]
                gender = row[idx_gender]
                phone_number = row[idx_phone_number]
                birth_date = row[idx_birth_date]
                ssn = row[idx_ssn]
                lon = row[idx_lon]
                lat = row[idx_lat]
                model = default_model
                start = start_day + random.randrange(start_range) if (
                        start_day is not None and start_range is not None) else -1
                end = end_day - random.randrange(end_range) if (end_day is not None and end_range is not None) else -1

                attr = {"first_name": first_name, "last_name": last_name, "street_addr": street_addr,
                        "city": city, "state": state, "zip": zip_code, "gender": gender, "phone_number": phone_number,
                        "birth_date": birth_date, "ssn": ssn, "lon": lon, "lat": lat}

                init_balance = random.uniform(min_balance, max_balance)  # Generate the initial balance
                self.add_account(aid, init_balance, start, end, default_country, default_acct_type, model, **attr)
                count += 1

    def load_account_param(self, acct_file):
        """Load and add account vertices from a CSV file with aggregated parameters
        Each row may represent two or more accounts
        :param acct_file: Account parameter file path
        :return:
        """

        idx_num = None  # Number of accounts per row
        idx_min = None  # Minimum initial balance
        idx_max = None  # Maximum initial balance
        idx_start = None  # Start step
        idx_end = None  # End step
        idx_country = None  # Country
        idx_business = None  # Business type
        idx_model = None  # Transaction model

        with open(acct_file, "r") as rf:
            reader = csv.reader(rf)
            # Parse header
            header = next(reader)
            for i, k in enumerate(header):
                if k == "count":
                    idx_num = i
                elif k == "min_balance":
                    idx_min = i
                elif k == "max_balance":
                    idx_max = i
                elif k == "start_day":
                    idx_start = i
                elif k == "end_day":
                    idx_end = i
                elif k == "country":
                    idx_country = i
                elif k == "business_type":
                    idx_business = i
                elif k == "model":
                    idx_model = i
                else:
                    print("Warning: unknown key: %s" % k)

            aid = 0
            for row in reader:
                if row[0].startswith("#"):
                    continue
                num = int(row[idx_num])
                min_balance = parse_amount(row[idx_min])
                max_balance = parse_amount(row[idx_max])
                start_day = parse_int(row[idx_start]) if idx_start is not None else -1
                end_day = parse_int(row[idx_end]) if idx_end is not None else -1
                country = row[idx_country]
                business = row[idx_business]
                # suspicious = parse_flag(row[idx_suspicious])
                modelID = parse_int(row[idx_model])

                for i in range(num):
                    init_balance = random.uniform(min_balance, max_balance)  # Generate amount
                    self.add_account(aid, init_balance, start_day, end_day, country, business, modelID)
                    aid += 1

        self.num_accounts = aid
        print("Created %d accounts." % self.num_accounts)

    # Generate base transactions from same degree sequences of transaction CSV
    def generate_normal_transactions(self):

        def get_degrees(deg_csv, num_v):
            """
            :param deg_csv: Degree distribution parameter CSV file
            :param num_v: Number of total account vertices
            :return: In-degree and out-degree sequence list
            """
            _in_deg = list()  # In-degree sequence
            _out_deg = list()  # Out-degree sequence
            with open(deg_csv, "r") as rf:  # Load in/out-degree sequences from parameter CSV file for each account
                reader = csv.reader(rf)
                next(reader)
                for row in reader:
                    if row[0].startswith("#"):
                        continue
                    nv = int(row[0])
                    _in_deg.extend(int(row[1]) * [nv])
                    _out_deg.extend(int(row[2]) * [nv])

            # print(len(in_deg), len(out_deg))
            assert len(_in_deg) == len(_out_deg), "In/Out-degree Sequences must have equal length."
            total_v = len(_in_deg)

            # If the number of total accounts from degree sequences is larger than specified, shrink degree sequence
            if total_v > num_v:
                diff = total_v - num_v  # The number of extra accounts to be removed
                in_tmp = list()
                out_tmp = list()
                for i in range(total_v):
                    num_in = _in_deg[i]
                    num_out = _out_deg[i]
                    # Remove element from in/out-degree sequences with the same number
                    if num_in == num_out and diff > 0:
                        diff -= 1
                    else:
                        in_tmp.append(num_in)
                        out_tmp.append(num_out)
                _in_deg = in_tmp
                _out_deg = out_tmp

            # If the number of total accounts from degree sequences is smaller than specified, extend degree sequence
            else:
                repeats = num_v // total_v  # Number of repetitions of degree sequences
                # print(len(in_deg), len(out_deg), repeats)
                _in_deg = _in_deg * repeats
                _out_deg = _out_deg * repeats
                # print(len(in_deg))
                remain = num_v - total_v * repeats  # Number of extra accounts
                _in_deg.extend([1] * remain)  # Add 1-degree account vertices
                _out_deg.extend([1] * remain)

            assert sum(_in_deg) == sum(_out_deg), "Sequences must have equal sums."
            return _in_deg, _out_deg

        def _directed_configuration_model(_in_deg, _out_deg, seed=0):
            """Return a directed_random graph with the given degree sequences without self loop.
            Based on nx.generators.degree_seq.directed_configuration_model
            :param _in_deg: Each list entry corresponds to the in-degree of a node.
            :param _out_deg: Each list entry corresponds to the out-degree of a node.
            :param seed: Seed for random number generator
            :return: MultiDiGraph without self loop
            """
            if not sum(_in_deg) == sum(_out_deg):
                raise nx.NetworkXError('Invalid degree sequences. Sequences must have equal sums.')

            random.seed(seed)
            n_in = len(_in_deg)
            n_out = len(_out_deg)
            if n_in < n_out:
                _in_deg.extend((n_out - n_in) * [0])
            else:
                _out_deg.extend((n_in - n_out) * [0])

            num_nodes = len(_in_deg)
            _g = nx.empty_graph(num_nodes, nx.MultiDiGraph())
            if num_nodes == 0 or max(_in_deg) == 0:
                return _g  # No edges

            in_stublist = list()
            out_stublist = list()
            for n in _g.nodes():
                in_stublist.extend(_in_deg[n] * [n])
                out_stublist.extend(_out_deg[n] * [n])
            random.shuffle(in_stublist)
            random.shuffle(out_stublist)

            num_edges = len(in_stublist)
            for i in range(num_edges):
                _src = out_stublist[i]
                _dst = in_stublist[i]
                if _src == _dst:  # ID conflict causes self-loop
                    for j in range(i + 1, num_edges):
                        # print("Conflict ID %d at %d" % (_src, i))
                        if _src != in_stublist[j]:
                            # print("Swap %d (%d) and %d (%d)" % (in_stublist[i], i, in_stublist[j], j))
                            in_stublist[i], in_stublist[j] = in_stublist[j], in_stublist[i]  # Swap ID
                            break

            _g.add_edges_from(zip(out_stublist, in_stublist))
            for idx, (_src, _dst) in enumerate(_g.edges()):
                if _src == _dst:
                    print("Self loop from/to %d at %d" % (_src, idx))
            return _g

        deg_file = os.path.join(self.input_dir, self.degree_file)
        in_deg, out_deg = get_degrees(deg_file, self.num_accounts)
        # Generate a directed graph from degree sequences (not transaction graph)
        g = _directed_configuration_model(in_deg, out_deg, self.seed)
        # g = nx.generators.degree_seq.directed_configuration_model(in_deg, out_deg, seed=self.seed)

        print("Add %d base transactions" % g.number_of_edges())
        nodes = self.g.nodes()
        for src_i, dst_i in g.edges():
            assert (src_i != dst_i)
            src = nodes[src_i]
            dst = nodes[dst_i]
            self.add_transaction(src, dst)  # Add edges to transaction graph

    def add_account(self, aid, init_balance, start, end, country, business, model_id, **attr):
        """Add an account vertex
        :param aid: Account ID
        :param init_balance: Initial amount
        :param start: The day when the account opened
        :param end: The day when the account closed
        :param country: Country
        :param business: business type
        :param model_id: Remittance model ID
        :param attr: Optional attributes
        :return:
        """
        # Add an account vertex with an ID and attributes if and only if an account with the same ID is not yet added
        if self.check_account_absent(aid):
            self.g.add_node(aid, label="account", init_balance=init_balance, start=start, end=end, country=country,
                            business=business, isFraud=False, modelID=model_id, **attr)

    def add_transaction(self, src, dst, amount=None, date=None, ttype=None):
        """Add a transaction edge
        :param src: Source account ID
        :param dst: Destination account ID
        :param amount: Transaction amount
        :param date: Transaction date
        :param ttype: Transaction type description
        :return:
        """
        self.check_account_exist(src)  # Ensure the source and destination accounts exist
        self.check_account_exist(dst)
        if src == dst:
            raise ValueError("Self loop from/to %s is not allowed for transaction networks" % str(src))
        self.g.add_edge(src, dst, key=self.tx_id, label="transaction", amount=amount, date=date, ttype=ttype)
        self.tx_id += 1
        if self.tx_id % 1000000 == 0:
            print("Added %d transactions" % self.tx_id)

    # Load Custom Topology Files
    def add_subgraph(self, members, topology):
        """Add subgraph from existing account vertices and given graph topology
        :param members: Account vertex list
        :param topology: Topology graph
        :return:
        """
        if len(members) != topology.number_of_nodes():
            raise nx.NetworkXError("The number of account vertices does not match")

        nodemap = dict(zip(members, topology.nodes()))
        for e in topology.edges():
            src = nodemap[e[0]]
            dst = nodemap[e[1]]
            self.add_transaction(src, dst)

    def load_edgelist(self, members, csv_name):
        """Load edgelist and add edges with existing account vertices
        :param members: Account vertex list
        :param csv_name: Edgelist file name
        :return:
        """
        topology = nx.MultiDiGraph()
        topology = nx.read_edgelist(csv_name, delimiter=",", create_using=topology)
        self.add_subgraph(members, topology)

    def load_alert_patterns(self):
        """Load an alert (fraud) parameter CSV file
        :return:
        """
        alert_file = os.path.join(self.input_dir, self.alert_file)

        idx_num = None
        idx_type = None
        idx_accts = None
        idx_schedule = None
        idx_individual = None
        idx_aggregated = None
        idx_count = None
        idx_difference = None
        idx_period = None
        idx_rounded = None
        idx_orig_country = None
        idx_bene_country = None
        idx_orig_business = None
        idx_bene_business = None
        idx_fraud = None

        with open(alert_file, "r") as rf:
            reader = csv.reader(rf)
            # Parse header
            header = next(reader)
            for i, k in enumerate(header):
                if k == "count":
                    idx_num = i
                elif k == "type":
                    idx_type = i
                elif k == "accounts":
                    idx_accts = i
                elif k == "individual_amount":
                    idx_individual = i
                elif k == "schedule_id":
                    idx_schedule = i
                elif k == "aggregated_amount":
                    idx_aggregated = i
                elif k == "transaction_count":
                    idx_count = i
                elif k == "amount_difference":
                    idx_difference = i
                elif k == "period":
                    idx_period = i
                elif k == "amount_rounded":
                    idx_rounded = i
                elif k == "orig_country":
                    idx_orig_country = i
                elif k == "bene_country":
                    idx_bene_country = i
                elif k == "orig_business":
                    idx_orig_business = i
                elif k == "bene_business":
                    idx_bene_business = i
                elif k == "is_fraud":
                    idx_fraud = i
                else:
                    print("Warning: unknown key: %s" % k)

            # Generate transaction set
            count = 0
            for row in reader:
                if row[0].startswith("#"):
                    continue
                num = int(row[idx_num])
                pattern_type = row[idx_type]
                accounts = int(row[idx_accts])
                scheduleID = int(row[idx_schedule])
                individual_amount = parse_amount(row[idx_individual])
                aggregated_amount = parse_amount(row[idx_aggregated])
                transaction_count = parse_int(row[idx_count])
                amount_difference = parse_amount(row[idx_difference])
                period = parse_int(row[idx_period]) if idx_period is not None else self.total_steps
                amount_rounded = parse_amount(row[idx_rounded]) if idx_rounded is not None else 0.0
                orig_country = parse_flag(row[idx_orig_country]) if idx_orig_country is not None else False
                bene_country = parse_flag(row[idx_bene_country]) if idx_bene_country is not None else False
                orig_business = parse_flag(row[idx_orig_business]) if idx_orig_business is not None else False
                bene_business = parse_flag(row[idx_bene_business]) if idx_bene_business is not None else False
                is_fraud = parse_flag(row[idx_fraud])

                if pattern_type not in self.alert_types:
                    print("Warning: pattern type (%s) must be one of %s" % (pattern_type, str(self.alert_types.keys())))
                    continue

                if transaction_count is not None and transaction_count < accounts:
                    print("Warning: number of transactions (%d) "
                          "must not be smaller than the number of accounts (%d)" % (transaction_count, accounts))
                    continue

                for i in range(num):
                    # Add alert patterns
                    self.add_alert_pattern(is_fraud, pattern_type, accounts, scheduleID, individual_amount,
                                           aggregated_amount, transaction_count, amount_difference, period,
                                           amount_rounded, orig_country, bene_country, orig_business, bene_business)
                    count += 1
                    if count % 1000 == 0:
                        print("Write %d alerts" % count)

    def add_alert_pattern(self, is_fraud, pattern_type, accounts, schedule_id=1, individual_amount=None,
                          aggregated_amount=None, transaction_freq=None,
                          amount_difference=None, period=None, amount_rounded=None,
                          orig_country=False, bene_country=False, orig_business=False, bene_business=False):
        """Add an AML rule transaction set
        :param is_fraud: Whether the transaction set is fraud or alert
        :param pattern_type: Pattern type ("fan_in", "fan_out", "dense", "mixed" or "stack")
        :param accounts: Number of transaction members (accounts)
        :param schedule_id: AML pattern transaction schedule model ID
        :param individual_amount: Minimum individual amount
        :param aggregated_amount: Minimum aggregated amount
        :param transaction_freq: Minimum transaction frequency
        :param amount_difference: Proportion of maximum transaction difference
        :param period: Lookback period (days)
        :param amount_rounded: Proportion of rounded amounts
        :param orig_country: Whether the originator country is suspicious
        :param bene_country: Whether the beneficiary country is suspicious
        :param orig_business: Whether the originator business type is suspicious
        :param bene_business: Whether the beneficiary business type is suspicious
        :return:
        """
        subject, members = self.get_alert_members(accounts, is_fraud)

        # Prepare parameters
        if individual_amount is None:
            min_amount = self.default_min_amount
            max_amount = self.default_max_amount
        else:
            min_amount = individual_amount
            max_amount = individual_amount * 2

        if aggregated_amount is None:
            aggregated_amount = 0

        start_day = 0
        end_day = self.total_steps

        # Create subgraph structure with transaction attributes
        modelID = self.alert_types[pattern_type]  # alert model ID
        sub_g = nx.MultiDiGraph(modelID=modelID, reason=pattern_type, scheduleID=schedule_id, start=start_day,
                                end=end_day)  # Transaction subgraph for an alert
        num_members = len(members)  # Number of accounts
        total_amount = 0
        transaction_count = 0

        if pattern_type == "fan_in":  # fan_in pattern (multiple accounts --> single (subject) account)
            src_list = [n for n in members if n != subject]
            dst = subject
            if transaction_freq is None:
                transaction_freq = num_members - 1
            for src in itertools.cycle(src_list):  # Generate transactions for the specified number
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(src, dst, amount=amount, date=date)
                self.g.add_edge(src, dst, amount=amount, date=date)
                transaction_count += 1
                total_amount += amount
                if transaction_count >= transaction_freq and total_amount >= aggregated_amount:
                    break

        elif pattern_type == "fan_out":  # fan_out pattern (single (subject) account --> multiple accounts)
            src = subject
            dst_list = [n for n in members if n != subject]
            if transaction_freq is None:
                transaction_freq = num_members - 1
            for dst in itertools.cycle(dst_list):  # Generate transactions for the specified number
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(src, dst, amount=amount, date=date)
                self.g.add_edge(src, dst, amount=amount, date=date)

                transaction_count += 1
                total_amount += amount
                if transaction_count >= transaction_freq and total_amount >= aggregated_amount:
                    break

        elif pattern_type == "bipartite":  # bipartite (sender accounts --> all-to-all --> receiver accounts)
            src_list = members[:(num_members // 2)]  # The former half members are sender accounts
            dst_list = members[(num_members // 2):]  # The latter half members are receiver accounts
            if transaction_freq is None:  # Number of transactions
                transaction_freq = len(src_list) * len(dst_list)
            for src, dst in itertools.product(src_list, dst_list):  # All-to-all transactions
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(src, dst, amount=amount, date=date)
                self.g.add_edge(src, dst, amount=amount, date=date)

                transaction_count += 1
                total_amount += amount
                if transaction_count > transaction_freq and total_amount >= aggregated_amount:
                    break

        elif pattern_type == "mixed":  # fan_out -> bipartite -> fan_in
            src = members[0]  # Source account
            dst = members[num_members - 1]  # Destination account
            src_list = members[1:(num_members // 2)]  # First intermediate accounts
            dst_list = members[(num_members // 2):num_members - 1]  # Second intermediate accounts

            if transaction_freq is None:
                transaction_freq = len(src_list) + len(dst_list) + len(src_list) * len(dst_list)

            for _dst in src_list:  # Fan-out
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(src, _dst, amount=amount, date=date)
                self.g.add_edge(src, _dst, amount=amount, date=date)
                transaction_count += 1
                total_amount += amount

            for _src, _dst in itertools.product(src_list, dst_list):  # Bipartite
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(_src, _dst, amount=amount, date=date)
                self.g.add_edge(_src, _dst, amount=amount, date=date)
                transaction_count += 1
                total_amount += amount

            for _src in itertools.cycle(dst_list):  # Fan-in
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(_src, dst, amount=amount, date=date)
                self.g.add_edge(_src, dst, amount=amount, date=date)
                transaction_count += 1
                total_amount += amount
                if transaction_count >= transaction_freq and total_amount >= aggregated_amount:
                    break

        elif pattern_type == "stack":  # two dense bipartite layers
            src_list = members[:num_members // 3]  # First 1/3 of members are source accounts
            mid_list = members[num_members // 3:num_members * 2 // 3]  # Second 1/3 of members are intermediate accounts
            dst_list = members[num_members * 2 // 3:]  # Last 1/3 of members are destination accounts
            if transaction_freq is None:  # Total number of transactions
                transaction_freq = len(src_list) * len(mid_list) + len(mid_list) * len(dst_list)

            for src, dst in itertools.product(src_list, mid_list):  # all-to-all transactions
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(src, dst, amount=amount, date=date)
                self.g.add_edge(src, dst, amount=amount, date=date)
                transaction_count += 1
                total_amount += amount
                if transaction_count > transaction_freq and total_amount >= aggregated_amount:
                    break
            for src, dst in itertools.product(mid_list, dst_list):  # all-to-all transactions
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(src, dst, amount=amount, date=date)
                self.g.add_edge(src, dst, amount=amount, date=date)
                transaction_count += 1
                total_amount += amount
                if transaction_count > transaction_freq and total_amount >= aggregated_amount:
                    break

        elif pattern_type == "dense":  # Dense alert accounts (all-to-all)
            dsts = [n for n in members if n != subject]
            for dst in dsts:
                amount = random.uniform(min_amount, max_amount)
                date = random.randrange(start_day, end_day)
                sub_g.add_edge(subject, dst, amount=amount, date=date)
                self.g.add_edge(subject, dst, amount=amount, date=date)
            for dst in dsts:
                nb1 = random.choice(dsts)
                if dst != nb1:
                    amount = random.uniform(min_amount, max_amount)
                    date = random.randrange(start_day, end_day)
                    sub_g.add_edge(dst, nb1, amount=amount, date=date)
                    self.g.add_edge(dst, nb1, amount=amount, date=date)
                nb2 = random.choice(dsts)
                if dst != nb2:
                    amount = random.uniform(min_amount, max_amount)
                    date = random.randrange(start_day, end_day)
                    sub_g.add_edge(nb2, dst, amount=amount, date=date)
                    self.g.add_edge(nb2, dst, amount=amount, date=date)

        elif pattern_type == "cycle":  # Cycle transactions
            subject_index = list(members).index(subject)  # Index of member list indicates the subject account
            num = len(members)  # Number of involved accounts
            amount = random.uniform(min_amount, max_amount)  # Transaction amount
            dates = sorted([random.randrange(start_day, end_day) for _ in range(num)])  # Transaction date (in order)
            for i in range(num):
                src_i = (subject_index + i) % num
                dst_i = (src_i + 1) % num
                src = members[src_i]  # Source account ID
                dst = members[dst_i]  # Destination account ID
                date = dates[i]  # Transaction date (timestamp)

                sub_g.add_edge(src, dst, amount=amount, date=date)
                self.g.add_edge(src, dst, amount=amount, date=date)

        else:
            print("Warning: unknown pattern type: %s" % pattern_type)
            return

        # Add the generated transaction edges to whole transaction graph
        sub_g.graph["subject"] = subject if is_fraud else None
        self.alert_groups[self.alert_id] = sub_g

        # Add the fraud flag to the subject account vertex
        if is_fraud:
            self.g.node[subject]["isFraud"] = True
        # for n in sub_g.nodes():
        #     self.g.node[n]["isFraud"] = True
        self.alert_id += 1

    def write_account_list(self):
        """Write all account list
        """
        os.makedirs(self.output_dir, exist_ok=True)
        fname = os.path.join(self.output_dir, self.out_account_file)
        with open(fname, "w") as wf:
            writer = csv.writer(wf)
            base_attrs = ["ACCOUNT_ID", "CUSTOMER_ID", "INIT_BALANCE", "START_DATE", "END_DATE", "COUNTRY",
                          "ACCOUNT_TYPE", "IS_FRAUD", "TX_BEHAVIOR_ID"]
            writer.writerow(base_attrs + self.attr_names)
            for n in self.g.nodes(data=True):
                aid = n[0]  # Account ID
                cid = "C_" + str(aid)  # Customer ID bounded to this account
                prop = n[1]  # Account attributes
                balance = "{0:.2f}".format(prop["init_balance"])  # Initial balance
                start = prop["start"]  # Start time (when the account is opened)
                end = prop["end"]  # End time (when the account is closed)
                country = prop["country"]  # Country
                business = prop["business"]  # Business type
                # suspicious = prop["suspicious"]  # Whether this account is suspicious (unused)
                isFraud = "true" if prop[
                    "isFraud"] else "false"  # Whether this account is involved in fraud transactions
                modelID = prop["modelID"]  # Transaction behavior model ID
                values = [aid, cid, balance, start, end, country, business, isFraud, modelID]
                for attr_name in self.attr_names:
                    values.append(prop[attr_name])
                writer.writerow(values)
        print("Exported %d accounts." % self.g.number_of_nodes())

    def write_transaction_list(self):
        tx_file = os.path.join(self.output_dir, self.out_tx_file)
        with open(tx_file, "w") as wf:
            writer = csv.writer(wf)
            writer.writerow(["id", "src", "dst", "ttype"])
            for e in self.g.edges(data=True, keys=True):
                src = e[0]
                dst = e[1]
                tid = e[2]
                ttype = random.choice(self.tx_types)
                writer.writerow([tid, src, dst, ttype])
        print("Exported %d transactions." % self.g.number_of_edges())

    def write_alert_members(self):
        """Write alert account list
        """

        def get_out_edge_attrs(g, vid, name):
            return [v for k, v in nx.get_edge_attributes(g, name).items() if (k[0] == vid or k[1] == vid)]

        acct_count = 0
        alert_file = os.path.join(self.output_dir, self.out_alert_file)
        with open(alert_file, "w") as wf:
            writer = csv.writer(wf)
            base_attrs = ["alertID", "reason", "clientID", "isSubject", "modelID", "minAmount", "maxAmount",
                          "startStep", "endStep", "scheduleID"]
            writer.writerow(base_attrs + self.attr_names)
            for gid, sub_g in self.alert_groups.items():
                modelID = sub_g.graph["modelID"]
                scheduleID = sub_g.graph["scheduleID"]
                reason = sub_g.graph["reason"]
                start = sub_g.graph["start"]
                end = sub_g.graph["end"]
                for n in sub_g.nodes():
                    isSubject = "true" if (sub_g.graph["subject"] == n) else "false"
                    minAmount = '{:.2f}'.format(min(get_out_edge_attrs(sub_g, n, "amount")))
                    maxAmount = '{:.2f}'.format(max(get_out_edge_attrs(sub_g, n, "amount")))
                    minStep = start
                    maxStep = end
                    values = [gid, reason, n, isSubject, modelID, minAmount, maxAmount, minStep, maxStep, scheduleID]
                    prop = self.g.node[n]
                    for attr_name in self.attr_names:
                        values.append(prop[attr_name])
                    writer.writerow(values)
                    acct_count += 1

        print("Exported %d members for %d alerted groups." % (acct_count, len(self.alert_groups)))


if __name__ == "__main__":
    argv = sys.argv
    if len(argv) < 2:
        print("Usage: python3 %s [ConfJSON]" % argv[0])
        exit(1)

    _conf_file = argv[1]

    txg = TransactionGenerator(_conf_file)
    txg.load_account_list()  # Load account list CSV file
    txg.generate_normal_transactions()  # Load a parameter CSV file for the base transaction types
    txg.set_subject_candidates()  # Load a parameter CSV file for degrees of the base transaction graph
    txg.load_alert_patterns()
    txg.write_account_list()  # Export accounts to a CSV file
    txg.write_transaction_list()  # Export transactions to a CSV file
    txg.write_alert_members()  # Export alert accounts to a CSV file
