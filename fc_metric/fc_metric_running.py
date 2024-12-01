import pandas as pd
from tqdm import tqdm

from fc_metric import calculate_fc_using_gpt

tqdm.pandas()

filename = "repo_filtered_data_DOIs_vetle.csv"
df = pd.read_csv("../data/identifiers_and_abstracts" + filename)
df["fc_metric"] = df.progress_apply(
    lambda x: calculate_fc_using_gpt(
        x["sem_scholar_abstract"], x["title"], x["sem_scholar_title"], False
    ),
    axis=1,
)

df.to_csv("./" + filename, index=False)
