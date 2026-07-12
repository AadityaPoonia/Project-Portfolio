package uk.ac.gla.dcs.bigdata.studentfunctions;

import java.util.Iterator;

import org.apache.spark.api.java.function.FlatMapFunction;

import uk.ac.gla.dcs.bigdata.providedstructures.Query;

/**
 * Returns the query term strings of a query.
 *
 */
public class QueryFlatMap implements FlatMapFunction<Query, String> {

	private static final long serialVersionUID = -94072484638950630L;

	@Override
	public Iterator<String> call(Query t) throws Exception {
		
		// Return the query terms of the query in an iterator.
		return t.getQueryTerms().iterator();
	}

}
