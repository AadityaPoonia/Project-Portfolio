package uk.ac.gla.dcs.bigdata.studentstructures;

import java.io.Serializable;

import uk.ac.gla.dcs.bigdata.providedstructures.NewsArticle;
import uk.ac.gla.dcs.bigdata.providedstructures.Query;

//Represents the DPH for each query-article pair.
public class QueryArticleScore implements Serializable {
	
	private static final long serialVersionUID = 3170295153204812411L;
	
	String docid; // The doc id of the article.
	Query query; // The query. 
	NewsArticle article; // The news article.
	double score; // the total DPH score 
	
	public QueryArticleScore() {};
	
	public QueryArticleScore(String docid, Query query,NewsArticle article,double score) {
		
		super();
		this.docid = docid;
		this.query = query;
		this.article=article;
		this.score = score;
	}

	public NewsArticle getArticle() {
		return article;
	}

	public void setArticle(NewsArticle article) {
		this.article = article;
	}

	public String getDocid() {
		return docid;
	}


	public void setDocid(String id) {
		this.docid = id;
	}

	public Query getQuery() {
		return query;
	}

	public void setQuery(Query query) {
		this.query = query;
	}

	public double getScore() {
		return score;
	}

	public void setScore(double score) {
		this.score = score;
	}
	
	
}
