import pandas as pd

from fc_metric import calculate_fc_using_gpt

filename = "filtered_data_with_abstracts_repo.csv"
df = pd.read_csv("../data/" + filename)
df["fc_metric"] = df.apply(
    lambda x: calculate_fc_using_gpt(
        x["sem_scholar_abstract"], x["title"], x["sem_scholar_title"], False
    ),
    axis=1,
)

df.to_csv("./" + filename, index=False)
