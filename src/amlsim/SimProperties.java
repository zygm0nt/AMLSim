package amlsim;

import java.io.*;
import java.nio.file.*;
import org.json.*;

public class SimProperties {

    private static final String separator = File.separator;
    private JSONObject obj;
    private JSONObject generalProp;
    private JSONObject simProp;
    private JSONObject inputProp;
    private JSONObject outputProp;
    private JSONObject cashInProp;
    private JSONObject cashOutProp;
    private String simName;
    private String inputDir;
    private String outputDir;

    public SimProperties(String fname) throws IOException{
        String jsonStr = loadTextFile(fname);
        obj = new JSONObject(jsonStr);
        generalProp = obj.getJSONObject("general");
        simProp = obj.getJSONObject("simulator");
        inputProp = obj.getJSONObject("temporal");
        outputProp = obj.getJSONObject("output");
        cashInProp = obj.getJSONObject("default").getJSONObject("cash_in");
        cashOutProp = obj.getJSONObject("default").getJSONObject("cash_out");

        simName = generalProp.getString("simulation_name");
        inputDir = inputProp.getString("directory") + separator;
        outputDir = inputDir + separator + simName + separator;
    }

    public static String loadTextFile(String fname) throws IOException{
        Path file = Paths.get(fname);
        byte[] bytes = Files.readAllBytes(file);
        return new String(bytes);
    }

    public String getSimName(){
        return generalProp.getString("simulation_name");
    }

    public int getSeed(){
        return generalProp.getInt("random_seed");
    }

    public int getSteps(){
        return generalProp.getInt("total_steps");
    }

    public boolean isComputeDiameter(){
        return simProp.getBoolean("compute_diameter");
    }

    public int getTransactionLimit(){
        return simProp.getInt("transaction_limit");
    }

    public int getTransactionInterval(){
        return simProp.getInt("transaction_interval");
    }

    public int getNumBranches(){
        return simProp.getInt("numBranches");
    }

    public String getInputAcctFile(){
        return inputDir + inputProp.getString("accounts");
    }

    public String getInputTxFile(){
        return inputDir + inputProp.getString("transactions");
    }

    public String getInputAlertFile(){
        return inputDir + inputProp.getString("alert_members");
    }

    public String getOutputTxLogFile(){
        return outputDir + outputProp.getString("transaction_log");
    }

    public String getOutputAlertMemberFile(){
        return outputDir + outputProp.getString("alert_members");
    }

    public String getOutputAlertTxFile(){
        return outputDir + outputProp.getString("alert_transactions");
    }

    public String getOutputDir(){
        return outputDir;
    }

    public String getCounterLogFile(){
        return outputDir + outputProp.getString("counter_log");
    }

    public String getDiameterLogFile(){
        return outputDir + outputProp.getString("diameter_log");
    }

    public int getCashTxInterval(boolean isCashIn, boolean isFraud){
        String key = isFraud ? "fraud_interval" : "normal_interval";
        return isCashIn ? cashInProp.getInt(key) : cashOutProp.getInt(key);
    }

    public float getCashTxMinAmount(boolean isCashIn, boolean isFraud){
        String key = isFraud ? "fraud_min_amount" : "normal_min_amount";
        return isCashIn ? cashInProp.getFloat(key) : cashOutProp.getFloat(key);
    }

    public float getCashTxMaxAmount(boolean isCashIn, boolean isFraud){
        String key = isFraud ? "fraud_max_amount" : "normal_max_amount";
        return isCashIn ? cashInProp.getFloat(key) : cashOutProp.getFloat(key);
    }
}


