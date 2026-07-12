package uk.ac.gla.dcs.bigdata.studentfunctions;

import org.apache.spark.api.java.function.MapFunction;

import uk.ac.gla.dcs.bigdata.providedstructures.Query;
import uk.ac.gla.dcs.bigdata.studentstructures.QueryArticleScore;

/**
 * Returns the query from the ArticleQueryScore. 
 *
 */
public class QueryScoreToQuery implements MapFunction<QueryArticleScore, Query> {

	private static final long serialVersionUID = 3461040687521268325L;

	@Override
	public Query call(QueryArticleScore articleQueryScore) throws Exception {
		
		// Return the query from the ArticleQueryScore object.
		return articleQueryScore.getQuery();
	}

}
