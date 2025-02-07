package amlsim.model.normal;

import amlsim.AMLSim;
import amlsim.Account;
import amlsim.model.AbstractTransactionModel;

import java.util.*;

/**
 * Send money received from an account to another account in a similar way
 */
public class ForwardTransactionModel extends AbstractTransactionModel {
    private int index = 0;

    public void setParameters(int interval, float balance, long start, long end){
        super.setParameters(interval, balance, start, end);
        if(this.startStep < 0){  // decentralize the first transaction step
            this.startStep = generateStartStep(interval);
        }
    }

    @Override
    public String getType() {
        return "Forward";
    }

    @Override
    public void sendTransaction(long step) {

        float amount = getTransactionAmount();  // this.balance;
        List<Account> dests = this.account.getDests();
        int numDests = dests.size();
        if(numDests == 0){
            return;
        }
        if((step - startStep) % interval != 0){
            return;
        }

        if(index >= numDests){
            index = 0;
        }
        Account dest = dests.get(index);
        this.sendTransaction(step, amount, dest);
        index++;
    }
}
