package uk.ac.gla.dcs.bigdata.studentfunctions;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import org.apache.spark.api.java.function.FlatMapFunction;
import org.apache.spark.broadcast.Broadcast;

import scala.Tuple2;
import uk.ac.gla.dcs.bigdata.providedstructures.Query;
import uk.ac.gla.dcs.bigdata.providedutilities.DPHScorer;
import uk.ac.gla.dcs.bigdata.studentstructures.PostNewsArticle;
import uk.ac.gla.dcs.bigdata.studentstructures.QueryArticleScore;

//Calculates the DPH for each query for an article

public class QueryScoreFormaterMap implements FlatMapFunction<PostNewsArticle,QueryArticleScore>   {

	
	private static final long serialVersionUID = 7657428036496798076L;
	
	long Totaldocumentspresent;
	double Avgdoclength;
	
	Broadcast<List<Query>> broadcast_qlist;
	Broadcast<List<Tuple2<String, Integer>>> broadcast_totaltermfreq;
	
	public QueryScoreFormaterMap(Broadcast<List<Query>> broadcastQueries, Broadcast<List<Tuple2<String, Integer>>> broadcast_totaltermfreq, long totalDocsInCorpus, double averageDocumentLengthInCorpus) {
		this.broadcast_qlist = broadcastQueries;
		this.broadcast_totaltermfreq = broadcast_totaltermfreq;
		this.Totaldocumentspresent = totalDocsInCorpus;
		this.Avgdoclength = averageDocumentLengthInCorpus;
	}

	@Override
	public Iterator<QueryArticleScore> call(PostNewsArticle postNewsArticle) throws Exception {
		
		// Get the broadcasted queries and total term frequencies.
		List<Query> queries = broadcast_qlist.value();
		List<Tuple2<String, Integer>> totalTermFrequenciesInCorpus = broadcast_totaltermfreq.value();
		
		// Create an empty list of article query scores.
		List<QueryArticleScore> article_qscores = new ArrayList<QueryArticleScore>(queries.size());
		
		for (Query query: queries) {
			
			// Initialize the total DPH score to 0.
			double total_dph_score = 0;
			
			// Iterate through each query term for every query.
			for (String queryTerm: query.getQueryTerms()) {
				
				// Get the term frequency for the query term in the article.
				int term_freq_in_doc = 0;
				if (postNewsArticle.getDocumentTermCounts().get(queryTerm) != null) {
					term_freq_in_doc = postNewsArticle.getDocumentTermCounts().get(queryTerm);
				}
				
				// Get the total term frequency for the query term in the corpus from the broadcast.
				int total_termf_corpus = 0;
				for (Tuple2<String, Integer> ttf: totalTermFrequenciesInCorpus) {
					if (ttf._1.equals(queryTerm)) {
						total_termf_corpus = ttf._2;
						break;
					}
				}
				
				// Calculate the DPH score for the current query term.
				double current_dph_score = DPHScorer.getDPHScore(
						(short)term_freq_in_doc,
						total_termf_corpus,
						postNewsArticle.getCurrentDocumentLength(),
						Avgdoclength,
						Totaldocumentspresent);
				
				// If the current DPH score is NaN, set it to 0.
				if (Double.isNaN(current_dph_score)) current_dph_score = 0;
				
				// Sum the DPH scores.
				total_dph_score += current_dph_score;
			}
			
			// If the DPH score is greater than 0, add it to the articleQueryScores list.
			if (total_dph_score > 0)
			article_qscores.add(new QueryArticleScore(postNewsArticle.getId(), query, postNewsArticle.getArticle(), total_dph_score));
		}
		

		return article_qscores.iterator();
	}
}

