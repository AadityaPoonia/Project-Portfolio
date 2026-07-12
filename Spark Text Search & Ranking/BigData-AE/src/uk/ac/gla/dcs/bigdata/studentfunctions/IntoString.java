package uk.ac.gla.dcs.bigdata.studentfunctions;

import org.apache.spark.api.java.function.MapFunction;

import scala.Tuple2;

/**
 * This will return the String value from the Tuple.
 *
 */
public class IntoString implements MapFunction<Tuple2<String, Integer>, String> {

	private static final long serialVersionUID = -6611584729632806L;

	@Override
	public String call(Tuple2<String, Integer> tuple) throws Exception {
		return tuple._1;
	}
}
