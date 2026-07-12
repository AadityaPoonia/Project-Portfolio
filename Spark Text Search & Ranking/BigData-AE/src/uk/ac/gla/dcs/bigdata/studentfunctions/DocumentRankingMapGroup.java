package uk.ac.gla.dcs.bigdata.studentfunctions;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;

import org.apache.spark.api.java.function.MapGroupsFunction;

import uk.ac.gla.dcs.bigdata.providedstructures.DocumentRanking;
import uk.ac.gla.dcs.bigdata.providedstructures.Query;
import uk.ac.gla.dcs.bigdata.providedstructures.RankedResult;
import uk.ac.gla.dcs.bigdata.studentstructures.QueryArticleScore;

//returning the document ranking
 

public class DocumentRankingMapGroup implements MapGroupsFunction<Query, QueryArticleScore, DocumentRanking> {

	private static final long serialVersionUID = -4168175988891464530L;

	@Override
	public DocumentRanking call(Query key, Iterator<QueryArticleScore> values) throws Exception {
		
		// creating an empty DocumentRanking object and an empty list of RankedResults.
		DocumentRanking doc_ranking = new DocumentRanking();
		List<RankedResult> results = new ArrayList<RankedResult>();

		doc_ranking.setQuery(key);
		
	
		while (values.hasNext()) {
			QueryArticleScore article_qscore = values.next();
			results.add(new RankedResult(article_qscore.getDocid(),article_qscore.getArticle(), article_qscore.getScore()));
		}
		
		// sort in reverse
		Collections.sort(results);
		Collections.reverse(results);
		
		
		doc_ranking.setResults(results);
		
		// Return document ranking.
		return doc_ranking;
	}

}
