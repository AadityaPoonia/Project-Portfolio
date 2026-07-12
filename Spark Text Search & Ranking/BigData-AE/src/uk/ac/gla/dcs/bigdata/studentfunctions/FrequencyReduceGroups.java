package uk.ac.gla.dcs.bigdata.studentfunctions;
import org.apache.spark.api.java.function.ReduceFunction;

/**
 * Reducing the scores by summing.
 *
 */
public class FrequencyReduceGroups implements ReduceFunction<Integer> {

	private static final long serialVersionUID = -8374105962810039L;

	@Override
	public Integer call(Integer v1, Integer v2) throws Exception {
		
		return v1+v2; // returning sum of the scores
	}

}
