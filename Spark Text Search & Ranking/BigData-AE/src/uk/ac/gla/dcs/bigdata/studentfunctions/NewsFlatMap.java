package uk.ac.gla.dcs.bigdata.studentfunctions;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import org.apache.spark.api.java.function.FlatMapFunction;
import org.apache.spark.broadcast.Broadcast;

import uk.ac.gla.dcs.bigdata.providedstructures.NewsArticle;

/**
 * Filters NewsArticle objects based on a broadcast list of approved document IDs.
 * Returns a NewsArticle if its ID matches one from the broadcast list.
  * @param newsArticle The NewsArticle to check against approved IDs
 * @return Iterator over approved NewsArticle objects

 */
public class NewsFlatMap implements FlatMapFunction<NewsArticle, NewsArticle> {

    private static final long serialVersionUID = 8895477991579183745L;
  
    /** The broadcast list of approved document IDs to filter against */
    Broadcast<List<String>> broadcastDocIds;
  
    /**
     * Constructor taking the broadcast list of approved IDs.
     * @param broadcastDocIds The broadcast list of approved document IDs
 
     */
    public NewsFlatMap(Broadcast<List<String>> broadcastDocIds) {
      this.broadcastDocIds = broadcastDocIds;
    }
  
    @Override
    public Iterator<NewsArticle> call(NewsArticle newsArticle) throws Exception {
      
      // Get the latest approved doc IDs from the broadcast
      List<String> docIds = broadcastDocIds.value();
      
      // List to hold approved articles
      List<NewsArticle> approvedArticles = new ArrayList<>();
  
      // Check if news article ID is in approved list
      if (docIds.contains(newsArticle.getId())) {
        
        // ID matches approved list, add article to results
        approvedArticles.add(newsArticle);
      }
  
      // Return iterator over approved articles
      return approvedArticles.iterator();
    }
  
  }
