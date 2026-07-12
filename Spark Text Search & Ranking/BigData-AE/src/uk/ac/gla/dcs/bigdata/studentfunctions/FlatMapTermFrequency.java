package uk.ac.gla.dcs.bigdata.studentfunctions;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map.Entry;

import org.apache.spark.api.java.function.FlatMapFunction;
import org.apache.spark.broadcast.Broadcast;

import scala.Tuple2;
import uk.ac.gla.dcs.bigdata.studentstructures.PostNewsArticle;

/**
 * Converts the PostNewsArticle into a list of tuples, where each tuple represents a term and its frequency in any query.
 *
 */
public class FlatMapTermFrequency implements FlatMapFunction<PostNewsArticle, Tuple2<String, Integer>>{
	
	private static final long serialVersionUID = -86868374105962810L;
	
	Broadcast<List<String>> broadcast_qtermslist;

	public FlatMapTermFrequency(Broadcast<List<String>> broadcast_qtermslist) {
		this.broadcast_qtermslist = broadcast_qtermslist;
	}

	@Override
	public Iterator<Tuple2<String, Integer>> call(PostNewsArticle article) throws Exception {
		
		List<Tuple2<String,Integer>> term_frequencies = new ArrayList<Tuple2<String, Integer>>();
		List<String> qterms_list = broadcast_qtermslist.value();
		
		// For each term in the article, if the term exists in the list of query terms, include the term along with its count in the list.
		for(Entry<String, Integer> term: article.getDocumentTermCounts().entrySet()) {
			if (qterms_list.contains(term.getKey())) {
				term_frequencies.add(new Tuple2<String,Integer>(term.getKey(), term.getValue()));
			}
		}
		
		return term_frequencies.iterator();
	}
}

