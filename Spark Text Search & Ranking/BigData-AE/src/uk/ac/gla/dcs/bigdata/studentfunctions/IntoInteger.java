package uk.ac.gla.dcs.bigdata.studentfunctions;

import org.apache.spark.api.java.function.MapFunction;

import scala.Tuple2;

/**
 * This will return the integer value from the Tuple.
 *
 */
public class IntoInteger implements MapFunction<Tuple2<String, Integer>, Integer> {

	private static final long serialVersionUID = -399726348100454807L;

	@Override
	public Integer call(Tuple2<String, Integer> value) throws Exception {
		return value._2;
	}

}

