import argparse
import json
import random

import numpy as np
import torch
from tqdm import tqdm
from transformers import AutoTokenizer
from transformers import pipeline
from transformers.pipelines.pt_utils import KeyDataset

from util.datareader import TASK_ID_MAP
from util.datareader import load_inference_dataset


def enforce_reproducibility(seed=1000):
    # Sets seed manually for both CPU and CUDA
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    # For atomic operations there is currently
    # no simple way to enforce determinism, as
    # the order of parallel operations is not known.
    # CUDNN
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    # System based
    random.seed(seed)
    np.random.seed(seed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", help="Location of the data", required=True, type=str)
    parser.add_argument(
        "--task",
        help="Task to run",
        required=True,
        choices=list(TASK_ID_MAP.keys()),
        type=str,
    )
    parser.add_argument(
        "--outfile", help="Location to save data", required=True, type=str
    )

    parser.add_argument("--seed", type=int, help="Random seed", default=1000)
    parser.add_argument(
        "--model",
        help="Model ID or file location of model to use",
        default="roberta-base",
        type=str,
    )

    args = parser.parse_args()

    device = torch.device("cpu")
    if torch.cuda.is_available():
        print("Using CUDA")
        device = torch.device("cuda")

    seed = args.seed
    enforce_reproducibility(seed)

    tk = AutoTokenizer.from_pretrained(args.model)

    paper_dataset, news_dataset, tweet_dataset, original_data = load_inference_dataset(
        args.data, task=args.task
    )
    pipeline = pipeline(
        model=args.model,
        tokenizer=tk,
        device=device,
        task="text-classification",
        # function_to_apply='none' if args.task == 'sensationalism' else 'softmax', # Regression
        truncation="longest_first",
        max_length=512,
    )

    if args.task != "generalization":
        # Paper scores
        paper_id_to_score = {}
        for item, out in tqdm(
                zip(paper_dataset, pipeline(KeyDataset(paper_dataset, "text"))),
                desc="Scoring papers",
                total=len(paper_dataset),
        ):
            paper_id_to_score[item["article_id"]] = (
                out["score"]
                if args.task == "sensationalism"
                else int(out["label"].split("_")[1])
            )

        news_id_to_score = {}
        for item, out in tqdm(
                zip(news_dataset, pipeline(KeyDataset(news_dataset, "text"))),
                desc="Scoring articles",
                total=len(news_dataset),
        ):
            news_id_to_score[item["article_id"]] = (
                out["score"]
                if args.task == "sensationalism"
                else int(out["label"].split("_")[1])
            )

        tweet_id_to_score = {}
        for item, out in tqdm(
                zip(tweet_dataset, pipeline(KeyDataset(tweet_dataset, "text"))),
                desc="Scoring tweets",
                total=len(tweet_dataset),
        ):
            tweet_id_to_score[item["article_id"]] = (
                out["score"]
                if args.task == "sensationalism"
                else int(out["label"].split("_")[1])
            )

        # Now put the scores back in the original data and save
        with open(args.outfile, "wt") as f:
            for data in tqdm(original_data, desc="Writing scores"):
                for j, sentence in enumerate(data["full_paper_sentences"]):
                    sentence[args.task] = paper_id_to_score[f"{data['doi']}_{j}"]

                for news in data["news"]:
                    if "finding_sentences" in data["news"][news]:
                        for j, sentence in enumerate(
                                data["news"][news]["finding_sentences"]
                        ):
                            sentence[args.task] = news_id_to_score[f"{news}_{j}"]

                for j, tweet in enumerate(data["full_tweets"]):
                    tweet[args.task] = tweet_id_to_score[f"{data['doi']}_{j}"]
                f.write(json.dumps(data) + "\n")
    else:
        news_id_to_score = {}
        for item, out in tqdm(
                zip(news_dataset, pipeline(KeyDataset(news_dataset, "text"))),
                desc="Scoring articles",
                total=len(news_dataset),
        ):
            news_id_to_score[item["article_id"]] = int(out["label"].split("_")[1])

        tweet_id_to_score = {}
        for item, out in tqdm(
                zip(tweet_dataset, pipeline(KeyDataset(tweet_dataset, "text"))),
                desc="Scoring tweets",
                total=len(tweet_dataset),
        ):
            tweet_id_to_score[item["article_id"]] = int(out["label"].split("_")[1])

        # Now put the scores back in the original data and save
        with open(args.outfile, "wt") as f:
            for data in tqdm(original_data, desc="Writing scores"):
                for news in data["news"]:
                    if "finding_sentences" in data["news"][news]:
                        finding_sentence_scores = []
                        for j, sentence in enumerate(
                                data["news"][news]["finding_sentences"]
                        ):
                            for k, sentence in enumerate(data["full_paper_sentences"]):
                                if f"{news}_{j}_{k}" in news_id_to_score:
                                    finding_sentence_scores.append(
                                        news_id_to_score[f"{news}_{j}_{k}"]
                                    )
                                else:
                                    finding_sentence_scores.append(-1)
                            sentence[args.task] = finding_sentence_scores

                for j, tweet in enumerate(data["full_tweets"]):
                    finding_sentence_scores = []
                    for k, sentence in enumerate(data["full_paper_sentences"]):
                        if f"{data['doi']}_{j}_{k}" in tweet_id_to_score:
                            finding_sentence_scores.append(
                                tweet_id_to_score[f"{data['doi']}_{j}_{k}"]
                            )
                        else:
                            finding_sentence_scores.append(-1)
                    tweet[args.task] = finding_sentence_scores
                f.write(json.dumps(data) + "\n")
