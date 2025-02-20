import os

import pandas as pd
from openai import OpenAI

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError(
        "Please set the OPENAI_API_KEY environment variable before running the factual consistency metric script"
    )
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def calculate_fc_using_gpt(
    original_text, summary_text, original_title: None, fail_silent=True, return_prompt=False
) -> int:
    """
    Calculate the factual consistency score using GPT-4o-mini
    :param original_text: The original text to compare against
    :param summary_text: The summary text to evaluate
    :param original_title: The original title
    :param fail_silent: If True, return -1 if an error occurs, otherwise raise the error
    :return: The factual consistency score as an integer 0 to 100 (-1 if an error occurs)

    """
    taskins = "reddit post summarization given the referenced research abstract"
    aspect = "factual consistency or identical titles"
    antaspect = "inconsistencies or statements that can't be inferred"
    aspectins = "the degree to which the reddit summary can be inferred from the research abstract"

    try:
        prompt = (
            f'''Score the following {taskins} with respect to {aspect} on a discrete scale from 1 to 5, 
where a score of 1 means “{antaspect}” and score of one 5 means “perfect {aspect}”. 
Note that  {aspect} measures {aspectins}. 
{f"Research Title: {original_title}" if original_title else ""}
Research Abstract: {original_text}
Reddit Summary: {summary_text}  
Respond in the following format: '''
            + '{"score": *insert score here*}'
        )
        messages = [
                {
                    "role": "system",
                    "content": "You are an expert evaluator of scientific reddit posts.",
                },
                {"role": "user", "content": prompt},
            ]

        if return_prompt:
            return messages
        response = client.chat.completions.create(
            messages=messages,
            model="gpt-4o-mini",
            temperature=0,
        )

        gpt_score_json = response.choices[0].message.content
        gpt_score = eval(gpt_score_json).get("score", -1)
        # print(f"GPT Score: {gpt_score}")
        return int(gpt_score)
    except Exception as e:
        if not fail_silent:
            raise e
        print(
            f"Error: {e} for the following prompt: {prompt}, response: {gpt_score_json}, returning -1"
        )
        return -1


# Example usage
if __name__ == "__main__":
    df = pd.read_csv(
        "../data/mocked_fc_data.csv"
    )  # mock dataset for demonstration purposes
    for index, row in df.iterrows():
        original_text = row["research_abstract"]
        summary_text = row["reddit_post"]
        fc_score = calculate_fc_using_gpt(original_text, summary_text)
        df.at[index, "fc_score"] = fc_score
    df.to_csv("./data/mocked_fc_data_with_scores.csv", index=False)
