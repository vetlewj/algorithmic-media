Download whole folder from  [drive](https://drive.google.com/drive/folders/1DOLzsk7WaV5vXFL-X9-1QeVK0U9BDR_8?usp=drive_link)
# [Data](https://drive.google.com/drive/folders/1DOLzsk7WaV5vXFL-X9-1QeVK0U9BDR_8?usp=drive_link)
[combined_for_analysis_sensationalism_jargon_categories_domain_labels.csv](combined_for_analysis_sensationalism_jargon_categories_domain_labels.csv)

This file contains the combined data for the analysis. It contains the columns necessary for sensationalism, jargon, and domain labels analysis.  
`domain` is the domain of the article.  
`id` is the reddit identifier of the article.  
`is_top_domain_...` is a boolean indicating whether the domain is in the top ten most popular domains within the domain category.  
`jargon_proportion` is the proportion of jargon words in the title.  
`label_voting_...` is the label assigned to the domain by the respective method.  
`link_flair_text` is the flair (category) assigned to the reddit post.  
`month` is the month of the reddit post.  
`num_comments` is the number of comments on the reddit post.  
`score` is the score of the reddit post.  
`sensationalism_score` is the sensationalism score of the title.  
`title` is the title of the reddit post.  
`top_category` is the top science field of the post (grouped link_flairs).  
`url` is the url of the article.  
`year` is the year of the reddit post.

[domains_lm_and_manual_labeled.csv](domains_lm_and_manual_labeled.csv)
This file contains the domains and their labels manually and by the language model.  
## [science_jargon_sensationalism_csvs](science_jargon_sensationalism_csvs)
This contains 84 csv files, each containing the raw reddit posts for a specific month, including jargon and sensationalism scores, if possible.
When downloading the whole folder watch out, as some are marked spam by google drive and will not be downloaded.
## [identifiers_and_abstracts](identifiers_and_abstracts)
Contains the data for the identifiers and abstracts that we got from the semantic scholar api, as well as the corresponding fc tags.

**filtered_data**: filtered data meaning that this only contains the top domains. 

**_repo**: this suffix means that the data is only for the repositories, not for any of the other categories (news, scientific, etc.). The files without this suffix also contains scientific. We also searched through news, but we did not find any identifiers, and hence could not use these for semantic scholar api. 

**_with_identifiers**: these files contains the identifiers that we got from the urls by trying to filter for the identifiers that were available in semantic scholars apis (DOIs, arXiv links, PMID, and PMCID). 

**_with_abstracts**: these files contains the abstracts (and titles) that we got from the semantic scholar api using the aforementioned identifiers.

Following are including jareds data and should be considered the most up the final data for analysis

**{news, scientific, repo}_{details}_DOIs_fc_scores**: These files are the respective original files with the fc scores added.


## [eval](eval)
Contains the data for the evaluation of the different methods and metrics.

[summ_eval_model_annotations.aligned.jsonl](eval/summ_eval_model_annotations.aligned.jsonl)
This file contains the annotations for the evaluation of the factual consistency score gathered from https://github.com/Yale-LILY/SummEval?tab=readme-ov-file#human-annotations 

[summ_eval_model_annotations.aligned.with_lm_fc.csv](eval/summ_eval_model_annotations.aligned.with_lm_fc.csv) 
The results of the factual consistency score with the language model scores added. 
