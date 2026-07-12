package uk.ac.gla.dcs.bigdata.apps;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import org.apache.spark.api.java.JavaSparkContext;
import org.apache.spark.sql.Encoder;
import org.apache.spark.sql.KeyValueGroupedDataset;
import org.apache.spark.util.LongAccumulator;
import org.apache.spark.SparkConf;
import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Encoders;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;
import org.apache.spark.broadcast.Broadcast;
import scala.Tuple2;

import uk.ac.gla.dcs.bigdata.providedfunctions.NewsFormaterMap;
import uk.ac.gla.dcs.bigdata.providedfunctions.QueryFormaterMap;
import uk.ac.gla.dcs.bigdata.providedstructures.DocumentRanking;
import uk.ac.gla.dcs.bigdata.providedstructures.NewsArticle;
import uk.ac.gla.dcs.bigdata.providedstructures.Query;
import uk.ac.gla.dcs.bigdata.providedstructures.RankedResult;
import uk.ac.gla.dcs.bigdata.studentstructures.PostNewsArticle;
import uk.ac.gla.dcs.bigdata.studentfunctions.PostNewsFlatMap;
import uk.ac.gla.dcs.bigdata.studentfunctions.QueryFlatMap;
import uk.ac.gla.dcs.bigdata.studentfunctions.FlatMapTermFrequency;
import uk.ac.gla.dcs.bigdata.studentfunctions.FrequencyReduceGroups;
import uk.ac.gla.dcs.bigdata.studentfunctions.IntoInteger;
import uk.ac.gla.dcs.bigdata.studentfunctions.IntoString;
import uk.ac.gla.dcs.bigdata.studentfunctions.MapDocumentRanking;
import uk.ac.gla.dcs.bigdata.studentfunctions.NewsFlatMap;
import uk.ac.gla.dcs.bigdata.studentstructures.QueryArticleScore;
import uk.ac.gla.dcs.bigdata.studentfunctions.QueryScoreFormaterMap;
import uk.ac.gla.dcs.bigdata.studentfunctions.QueryScoreToQuery;
import uk.ac.gla.dcs.bigdata.studentfunctions.DocumentRankingMapGroup;

/**
 * This is the main class where your Spark topology should be specified.
 * 
 * By default, running this class will execute the topology defined in the
 * rankDocuments() method in local mode, although this may be overriden by
 * the spark.master environment variable.
 * @author Richard
 *
 */
public class AssessedExercise {

	
	public static void main(String[] args) {
		
		File hadoopDIR = new File("resources/hadoop/"); // represent the hadoop directory as a Java file so we can get an absolute path for it
		System.setProperty("hadoop.home.dir", hadoopDIR.getAbsolutePath()); // set the JVM system property so that Spark finds it
		
		// The code submitted for the assessed exerise may be run in either local or remote modes
		// Configuration of this will be performed based on an environment variable
		String sparkMasterDef = System.getenv("spark.master");
		if (sparkMasterDef==null) sparkMasterDef = "local[2]"; // default is local mode with two executors
		
		String sparkSessionName = "BigDataAE"; // give the session a name
		
		// Create the Spark Configuration 
		SparkConf conf = new SparkConf()
				.setMaster(sparkMasterDef)
				.setAppName(sparkSessionName);
		
		// Create the spark session
		SparkSession spark = SparkSession
				  .builder()
				  .config(conf)
				  .getOrCreate();
	
		
		// Get the location of the input queries
		String queryFile = System.getenv("bigdata.queries");
		if (queryFile==null) queryFile = "data/queries.list"; // default is a sample with 3 queries
		
		// Get the location of the input news articles
		String newsFile = System.getenv("bigdata.news");
		if (newsFile==null) newsFile = "data/TREC_Washington_Post_collection.v3.example.json"; // default is a sample of 5000 news articles
		
		// Call the student's code
		List<DocumentRanking> results = rankDocuments(spark, queryFile, newsFile);
		
		// Close the spark session
		spark.close();
		
		// Check if the code returned any results
		if (results==null) System.err.println("Topology return no rankings, student code may not be implemented, skiping final write.");
		else {
			
			// We have set of output rankings, lets write to disk
			
			// Create a new folder 
			File outDirectory = new File("results/"+System.currentTimeMillis());
			if (!outDirectory.exists()) outDirectory.mkdir();
			
			// Write the ranking for each query as a new file
			for (DocumentRanking rankingForQuery : results) {
				rankingForQuery.write(outDirectory.getAbsolutePath());
			}
		}
		
		
	}
	
	
	
	public static List<DocumentRanking> rankDocuments(SparkSession spark, String queryFile, String newsFile) {
		
		// Load queries and news articles
		Dataset<Row> queriesjson = spark.read().text(queryFile);
		Dataset<Row> newsjson = spark.read().text(newsFile); // read in files as string rows, one row per article
		
		// Perform an initial conversion from Dataset<Row> to Query and NewsArticle Java objects
		Dataset<Query> queries = queriesjson.map(new QueryFormaterMap(), Encoders.bean(Query.class)); // this converts each row into a Query
		Dataset<NewsArticle> news = newsjson.map(new NewsFormaterMap(), Encoders.bean(NewsArticle.class)); // this converts each row into a NewsArticle
		
		//----------------------------------------------------------------
		// Your Spark Topology should be defined here
		//----------------------------------------------------------------
		
		// 1)  Preprocessing news articles to get the values(Aaditya Poonia).
		
		// Creating accumulators to compute the total count of documents and the combined length of all documents in the corpus.
		
		LongAccumulator Doc_accumulator = spark.sparkContext().longAccumulator();
		LongAccumulator Doclength_accumulator = spark.sparkContext().longAccumulator();
				
		// We will specifically target three attributes: news ID, title, and content. Additionally, through news  
		// pre-processing, we will transform the news object into a post-processed news object containing
		// article tokens and their corresponding frequencies within the document.

		Encoder<PostNewsArticle> postnewsart_enc = Encoders.bean(PostNewsArticle.class);
		Dataset<PostNewsArticle> postnews_Articles =  news.flatMap(new PostNewsFlatMap(Doc_accumulator, Doclength_accumulator),postnewsart_enc);

		//2) Retrieving the frequencies of all query terms present in the corpus (Aaditya poonia)
		
		// Getting all the query terms.
		Dataset<String> query_terms = queries.flatMap(new QueryFlatMap(), Encoders.STRING());
		List<String> qtermslist = query_terms.collectAsList();
		
		// Creating a broadcast from the query terms list.
		Broadcast<List<String>> broadcast_qtermslist = JavaSparkContext.fromSparkContext(spark.sparkContext()).broadcast(qtermslist);
		
		// Using flatmap, getting all term frequencies for the query terms.
		Encoder<Tuple2<String, Integer>> termfrequency_enc = Encoders.tuple(Encoders.STRING(), Encoders.INT());
		Dataset<Tuple2<String, Integer>> term_frequencies = postnews_Articles.flatMap(new FlatMapTermFrequency(broadcast_qtermslist), termfrequency_enc);
		
		// Grouping term frequencies by the query term and mapping each query term to its frequency.
		IntoString keyFunction = new IntoString();
		IntoInteger valueFunction = new IntoInteger();
		KeyValueGroupedDataset<String, Integer> termfreq_grouped = term_frequencies.groupByKey(keyFunction, Encoders.STRING()).mapValues(valueFunction, Encoders.INT());
		
		// Reducing the groups to calculate the total term frequencies for each query term.
		Dataset<Tuple2<String, Integer>> termfreq_integers = termfreq_grouped.reduceGroups(new FrequencyReduceGroups());
		List<Tuple2<String, Integer>> totaltermfreq = termfreq_integers.collectAsList();
		
		// Getting the total number of documents in the corpus.
		long Totaldocumentspresent = Doc_accumulator.value();
		System.out.println("Number of documents in Corpus: " + Totaldocumentspresent);

		// Getting the total length of all the documents in the corpus.
		long Totaldoclength = Doclength_accumulator.value();
		System.out.println("Length of the documents: " + Totaldoclength);
		
		// Calculating the average document length of the corpus.
		double Avgdoclength = Totaldoclength*1.0 / Totaldocumentspresent;
		System.out.println("Average length of documents: " + Avgdoclength);	
		
		
		// 3) Calculating article query scores (Aditya Madhira)
		// creating a query list and broadcasting it 

		List<Query> qlist = queries.collectAsList();
		Broadcast<List<Query>> broadcast_qlist = JavaSparkContext.fromSparkContext(spark.sparkContext()).broadcast(qlist);

		//Broadcast of total query term frequencies
		Broadcast<List<Tuple2<String, Integer>>> broadcast_totaltermfreq = JavaSparkContext.fromSparkContext(spark.sparkContext()).broadcast(totaltermfreq);


		// Calculate the scores for each query and return a QueryArticleScore dataset
		Encoder<QueryArticleScore> article_qscore_enc = Encoders.bean(QueryArticleScore.class);
		Dataset<QueryArticleScore> article_qscores = postnews_Articles.flatMap(new QueryScoreFormaterMap(
			broadcast_qlist,
			broadcast_totaltermfreq,
			Totaldocumentspresent,
			Avgdoclength
		), article_qscore_enc);
		

		// 4) Ranking the docs (Aditya Madhira)
		// retrieve the queryscore dataset
		QueryScoreToQuery Key_function = new QueryScoreToQuery();
		KeyValueGroupedDataset<Query, QueryArticleScore> Articleqscore_grouped = article_qscores.groupByKey(Key_function, Encoders.bean(Query.class));


		//ranking and conversion to type DocumentRanking

		Encoder<DocumentRanking> documentRankingEncoder = Encoders.bean(DocumentRanking.class);
		Dataset<DocumentRanking> fullDocumentRanking = Articleqscore_grouped.mapGroups(new DocumentRankingMapGroup(), documentRankingEncoder);


		// Step 5: Remove duplicate documents from rankings (Rohit John Jacob)
        Dataset<DocumentRanking> dedupedRankings = fullDocumentRanking.map(new MapDocumentRanking(), documentRankingEncoder);

        List<DocumentRanking> dedupedRankingList = dedupedRankings.collectAsList();

        // Step 6: Retrieve full NewsArticle for each result (Rohit John Jacob)

       // Get list of unique doc IDs from deduped rankings
       List<String> docIds = new ArrayList<>();

       for(DocumentRanking ranking : dedupedRankingList) {
       for (RankedResult result : ranking.getResults()) {
       docIds.add(result.getDocid());
        }
      }

      // Broadcast list of IDs needed
      Broadcast<List<String>> broadcastDocIds = JavaSparkContext.fromSparkContext(spark.sparkContext()).broadcast(docIds);

      // Get just the NewsArticles we need
      Dataset<NewsArticle> topArticles = news.flatMap(new NewsFlatMap(broadcastDocIds), Encoders.bean(NewsArticle.class));

      List<NewsArticle> topArticlesList = topArticles.collectAsList();

     // Step 7: Populate the full NewsArticle into each result (Rohit John Jacob)
     for(DocumentRanking ranking : dedupedRankingList) {
     for (RankedResult result : ranking.getResults()) {
     for (NewsArticle article : topArticlesList) {
         if (result.getDocid().equals(article.getId())) {
           result.setArticle(article);
      }
    }
  }  
}

// Step 8: Print out final rankings (Rohit John Jacob)
   for(DocumentRanking ranking : dedupedRankingList) {
	System.out.println(ranking.getQuery().getOriginalQuery());
	for (RankedResult result: ranking.getResults()) {
		System.out.printf("%.2f: %s\n", result.getScore(), result.getArticle().getTitle());
	}
	System.out.println("\n***\n");
}


  return dedupedRankingList; // Return final rankings
				
	
		}
	
	
}
