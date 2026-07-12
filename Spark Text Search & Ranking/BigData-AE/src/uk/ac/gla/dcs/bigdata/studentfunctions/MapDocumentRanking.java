package uk.ac.gla.dcs.bigdata.studentfunctions;

import java.util.ArrayList;
import java.util.List;

import org.apache.spark.api.java.function.MapFunction;

import uk.ac.gla.dcs.bigdata.providedstructures.DocumentRanking;
import uk.ac.gla.dcs.bigdata.providedstructures.RankedResult;
import uk.ac.gla.dcs.bigdata.providedutilities.TextDistanceCalculator;


/**
 * This class removes near-duplicate documents from the DocumentRanking by filtering out ranked results 
* that have a title similarity of >= 0.5 to any result already in the filtered list.
*
* @param docRanking The original DocumentRanking to filter
* @return A new DocumentRanking with the near-duplicate results removed
*/
public class MapDocumentRanking implements MapFunction<DocumentRanking, DocumentRanking> {

    private static final long serialVersionUID = 8098722524879698702L;
  
    @Override
    public DocumentRanking call(DocumentRanking docRanking) throws Exception {
      
      // Create a list to hold the filtered results
      List<RankedResult> filteredResults = new ArrayList<RankedResult>(0);
      
      // Loop through the original ranked results
      outerLoop: 
      for(RankedResult result: docRanking.getResults()) {
  
        // Exit early if 10 filtered results are already found
        if (filteredResults.size() == 10) {
          break outerLoop; 
        }
  
        // Loop through the already filtered results  
        for(RankedResult filteredResult: filteredResults) {
  
          // If similarity between titles is >= 0.5, skip to next result
          if(TextDistanceCalculator.similarity(result.getArticle().getTitle(),
                                               filteredResult.getArticle().getTitle()) < 0.5) {
            continue outerLoop;
          }
        }
  
        // Otherwise, title is considered unique - add result to filtered list
        filteredResults.add(result);
      }
  
      // Return new DocumentRanking with only unique titles
      return new DocumentRanking(docRanking.getQuery(), filteredResults);
    }
  
  }