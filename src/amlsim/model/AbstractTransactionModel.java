package amlsim.model;

import amlsim.Account;
import amlsim.AMLSim;
import java.util.Random;

/**
 * Base class of transaction models
 */
public abstract class AbstractTransactionModel {

    // Transaction model ID
    public static final int SINGLE = 0;  // Make a single transaction to each neighbor account
    public static final int FANOUT = 1;  // Make transactions to all neighbor accounts
    public static final int FANIN = 2;
    public static final int MUTUAL = 3;
    public static final int FORWARD = 4;
    public static final int PERIODICAL = 5;

    private static Random rand = new Random();
    private static final int FLUCTUATION = 2;  // Fluctuation of the transaction interval TODO: Enable users to specify this value

    protected Account account;  // Account object
    protected int interval = 1; // Default transaction interval
    protected float balance;  // Current balance
    protected long startStep = -1;  // The first step of transactions
    protected long endStep = -1;  // The end step of transactions
    protected float transactionAmountRatio = 0.5F;  // The ratio of maximum total amount for transactions to current balance

    /**
     * Get the assumed number of transactions in this simulation
     * @return Number of total transactions
     */
    public int getNumberOfTransactions(){
        return (int)AMLSim.getNumOfSteps() / interval;
    }

    /**
     * Get the assumed amount of each transaction
     * @return Transaction amount
     */
    public float getTransactionAmount(){
        int totalCount = getNumberOfTransactions();
        float available = this.balance * transactionAmountRatio;
        return available / totalCount;
    }

    /**
     * Set an account object which has this model
     * @param account Account object
     */
    public void setAccount(Account account){
        this.account = account;
    }

    /**
     * Get the simulation step range when this model is valid
     * @return The total number of simulation steps
     */
    public int getStepRange(){
        // If "startStep" and/or "endStep" is undefined (-1), it tries to return the largest value
        long st = startStep >= 0 ? startStep : 0;
        long ed = endStep > 0 ? endStep : AMLSim.getNumOfSteps();
        return (int)(ed - st + 1);
    }

    /**
     * Return transaction type
     * @return Transaction type name
     */
    public abstract String getType();

    /**
     * Create transactions
     * @param step Current simulation step
     */
    public abstract void sendTransaction(long step);

    /**
     * Generate a difference of the simulation step
     * @return Difference of simulation step [step - FLUCTUATION, step + FLUCTUATION]
     */
    protected static int generateDiff(){
        int t = rand.nextInt(FLUCTUATION * 2 + 1);
        return t - FLUCTUATION;
    }

    /**
     * Generate the start transaction step (to decentralize transaction distribution)
     * @param range Simulation step range
     * @return random int value [0, range-1]
     */
    protected static int generateStartStep(int range){
        return rand.nextInt(range);
    }

    /**
     * Set initial parameters
     * This method will be called when the account is initialized
     * @param interval Transaction interval
     * @param balance Initial balance of the account
     * @param start Start simulation step (any transactions cannot be sent before this step)
     * @param end End step (any transactions cannot be sent after this step)
     */
    public void setParameters(int interval, float balance, long start, long end){
        this.interval = interval;
        setParameters(balance, start, end);
    }

    public void setParameters(float balance, long start, long end){
        this.balance = balance;
        this.startStep = start;
        this.endStep = end;
    }

    /**
     * Generate and register a transaction (for fraud transactions)
     * @param step Current simulation step
     * @param amount Transaction amount
     * @param orig Origin account
     * @param dest Destination account
     * @param isFraud Whether this transaction is fraud
     * @param aid Alert ID
     */
    protected void sendTransaction(long step, float amount, Account orig, Account dest, boolean isFraud, long aid){
        if(amount <= 0){  // Invalid transaction with no amount
            return;
        }
        String ttype = orig.getTxType(dest);
        AMLSim.handleTransaction(step, ttype, amount, orig, dest, isFraud, aid);
    }

    /**
     * Generate and register a transaction (for cash transactions)
     * @param step Current simulation step
     * @param amount Transaction amount
     * @param orig Origin account
     * @param dest Destination account
     * @param ttype Transaction type
     */
    protected void sendTransaction(long step, float amount, Account orig, Account dest, String ttype){
        AMLSim.handleTransaction(step, ttype, amount, orig, dest, false, -1);
    }

    /**
     * Generate and register a transaction (for normal transactions)
     * @param step Current simulation step
     * @param amount Transaction amount
     * @param orig Origin account
     * @param dest Destination account
     */
    protected void sendTransaction(long step, float amount, Account orig, Account dest){
        sendTransaction(step, amount, orig, dest, false, -1);
    }

    /**
     * Generate and register a transaction (for normal transactions)
     * @param step Current simulation step
     * @param amount Transaction amount
     * @param dest Destination account
     */
    protected void sendTransaction(long step, float amount, Account dest){
        this.sendTransaction(step, amount, this.account, dest);
    }

}
