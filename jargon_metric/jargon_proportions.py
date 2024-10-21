import os
import pandas as pd
import constants
from nlp_loader import nlp


def filter_text(text: str):
    """
    Tokenize the text, lowercase, and remove punctuation, stopwords
    """
    doc = nlp(text)
    words = [token.text.lower() for token in doc if not token.is_punct and not token.is_stop]
    return words


def calculate_jargon_metric(text: str, related_categories: [str] = None, threshold: float = 0.1):
    """
    Calculate the proportion of jargon words in a given text.

    1. Count the number of words that appear in the text
    2. Count the number of “jargon”-words for each category
        a. For each category, store the number of jargon words that appear in the text
    3. count proportions of words that are in the list of jargon
    """
    category_path = constants.PMI_SCORES
    words = filter_text(text)
    total_words = len(words)
    if total_words == 0:
        return {"NONE": 0}
    jargon_proportions = {}

    all_categories = os.listdir(os.path.join(category_path, str(threshold)))

    # Get all the categories that are in the reddit_category list and in the PMI_SCORES folder
    if related_categories:
        categories = list(set(all_categories).intersection(set(related_categories)))

    for category in categories:
        # File path is category path / threshold / category
        file_path = os.path.join(os.path.join(category_path, str(threshold)), category)
        data = pd.read_csv(file_path)

        jargon_words = len(set(words).intersection(set(data['word'].values)))
        # TODO: Should there be any weighting of the jargon words or just use threshold?
        jargon_proportions[category] = jargon_words / total_words

    return jargon_proportions


def get_top_n_jargon_categories(jargon_proportions, n=5):
    """
    Get the top n categories with the highest proportion of jargon words in the text.
    """
    sorted_jargon_proportions = sorted(jargon_proportions.items(), key=lambda x: x[1], reverse=True)
    top_n = sorted_jargon_proportions[:n]
    return top_n


if __name__ == "__main__":
    text = "Scholarly text is often laden with jargon, or specialized language that can facilitate efficient in-group communication within fields but hinder understanding for out-groups. In this work, we develop and validate an interpretable approach for measuring scholarly jargon from text. Expanding the scope of prior work which focuses on word types, we use word sense induction to also identify words that are widespread but overloaded with different meanings across fields. We then estimate the prevalence of these discipline-specific words and senses across hundreds of subfields, and show that word senses provide a complementary, yet unique view of jargon alongside word types. We demonstrate the utility of our metrics for science of science and computational sociolinguistics by highlighting two key social implications. First, though most fields reduce their use of jargon when writing for general-purpose venues, and some fields (e.g., biological sciences) do so less than others. Second, the direction of correlation between jargon and citation rates varies among fields, but jargon is nearly always negatively correlated with interdisciplinary impact. Broadly, our findings suggest that though multidisciplinary venues intend to cater to more general audiences, some fields' writing norms may act as barriers rather than bridges, and thus impede the dispersion of scholarly ideas."
    jargon_proportion = calculate_jargon_metric(text)
    top_10_jargon_categories = get_top_n_jargon_categories(jargon_proportion)
    print(top_10_jargon_categories)
    print("Done!")
