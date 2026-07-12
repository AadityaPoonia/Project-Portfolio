package uk.ac.gla.dcs.bigdata.studentstructures;

import java.io.Serializable;
import java.util.HashMap;

import uk.ac.gla.dcs.bigdata.providedstructures.NewsArticle;

/*
 * Represents a modified version of a NewsArticle with added information, including a HashMap that stores term frequencies and the document's length.
 */
public class PostNewsArticle implements Serializable {

	private static final long serialVersionUID = -8790870210613896654L;
	
	String id; // unique identifier for the article
	String title; // title of the article after stemming, stopword removal and tokenization
	int current_doclength; // length of the article after stemming, stopword removal and tokenization
	NewsArticle article; // the original article
	HashMap<String, Integer> doc_termcounts; // term frequencies of the article after stemming, stopword removal and tokenization

	
	public NewsArticle getArticle() {
		return article;
	}

	public void setArticle(NewsArticle article) {
		this.article = article;
	}

	public PostNewsArticle() {}
	
	public PostNewsArticle(String id, String title, int current_doclength,
			HashMap<String, Integer> doc_termcounts, NewsArticle article) {
		super();
		this.id = id;
		this.title = title;
		this.current_doclength = current_doclength;
		this.doc_termcounts = doc_termcounts;
		this.article = article;
	}
	
	public String getId() {
		return id;
	}
	public void setId(String id) {
		this.id = id;
	}
	public String getTitle() {
		return title;
	}
	public void setTitle(String string) {
		this.title = string;
	}
	public int getCurrentDocumentLength() {
		return current_doclength;
	}
	public void setCurrentDocumentLength(int current_doclength) {
		this.current_doclength = current_doclength;
	}
	public HashMap<String, Integer> getDocumentTermCounts() {
		return doc_termcounts;
	}
	public void setDocumentTermCounts(HashMap<String, Integer> doc_termcounts) {
		this.doc_termcounts = doc_termcounts;
	}
	public static long getSerialversionuid() {
		return serialVersionUID;
	}


}

