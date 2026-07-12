package uk.ac.gla.dcs.bigdata.studentfunctions;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;

import org.apache.spark.api.java.function.FlatMapFunction;
import org.apache.spark.util.LongAccumulator;

import uk.ac.gla.dcs.bigdata.providedstructures.ContentItem;
import uk.ac.gla.dcs.bigdata.providedstructures.NewsArticle;
import uk.ac.gla.dcs.bigdata.providedutilities.TextPreProcessor;
import uk.ac.gla.dcs.bigdata.studentstructures.PostNewsArticle;

/**
 * This will convert the NewsArticle into PostNewsFormater.
 *
 */
public class PostNewsFlatMap implements FlatMapFunction<NewsArticle,PostNewsArticle>   {

	private static final long serialVersionUID = -74563856101202046L;
	
	LongAccumulator Doc_accumulator;
	LongAccumulator Doclength_accumulator;
	
	public PostNewsFlatMap(LongAccumulator Doc_accumulator, LongAccumulator Doclength_accumulator) {
		this.Doc_accumulator = Doc_accumulator;
		this.Doclength_accumulator = Doclength_accumulator;
	}


	@Override
	public Iterator<PostNewsArticle> call(NewsArticle news) throws Exception {	
		
	    // handles null case
		if(news == null)
		    return new ArrayList<PostNewsArticle>(0).iterator();
	    // handles null title 
		if(news.getTitle()== null)
		    return new ArrayList<PostNewsArticle>(0).iterator();
	
		//Initialising needed objects for this function
		TextPreProcessor textpreproc = new TextPreProcessor();
		List<String> postnewsarticle_full = new ArrayList<String>();
			
		// We aim to retrieve only 5 sub-contents of type "paragraph".
		// Iterating over all sub-contents, we filter out those meeting the specified criteria and increment this counter accordingly.
		int counter=0;
		
		// Loop around all sub-content and select first 5 of type "Paragraph"
		//performs tokenization, stop-word removal and stemming on the input text(content)
		if (news.getContents() != null) 
		for (ContentItem sub : news.getContents()) {
			// stop looking for sub-content after 5 sub-contents are found
			if(counter == 5)
				break;
			if(sub !=null)
			if(sub.getSubtype()!=null) {
				if(sub.getSubtype().toLowerCase().equals("paragraph")){
					postnewsarticle_full.addAll(textpreproc.process(sub.getContent()));
					counter++;
				}
			}
		}
			
		
		//Initialising needed objects after everything is passed
		HashMap<String, Integer> doc_termcounts = new HashMap<String, Integer>();
		List<PostNewsArticle> postnewsart_list_full = new ArrayList<PostNewsArticle>(1);
		
		
		// Tokenizes the input text (title), removes stop-words, and applies stemming.
		// Adds the title to the document terms.
		postnewsarticle_full.addAll(textpreproc.process(news.getTitle()));
		
		
		// Getting document length of all terms
		int doclength_terms=postnewsarticle_full.size();
		
		// Adding document length to accumulator.
		Doclength_accumulator.add(doclength_terms);
		
		// Adding document count to accumulator.
		Doc_accumulator.add(1);
		
		// The count of occurrences of each term across the documents, similar to a bag-of-words representation.
		for (String term : postnewsarticle_full) doc_termcounts.put(term, doc_termcounts.get(term)!= null? doc_termcounts.get(term)+1:1);

		// Adding all elements together
		postnewsart_list_full.add(new PostNewsArticle(news.getId(), news.getTitle(), doclength_terms,
		        doc_termcounts, new NewsArticle(null,null,news.getTitle(), null, 0, null, null, null)));
		
		return postnewsart_list_full.iterator();
	}

	

	
	
}
