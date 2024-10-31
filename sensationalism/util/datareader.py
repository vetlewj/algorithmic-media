import json
from collections import defaultdict
from functools import partial

import pandas as pd
from datasets import load_dataset, Dataset, DatasetDict, Value
from tqdm import tqdm


class LabelPassthrough(object):
    def __getitem__(self, x):
        return x

    def __len__(self):
        return 1

    def values(self):
        return [0]


CAUSAILTY_LABEL_MAP = {
    'Unclear relation': 0,
    'Explicitly states: no relation': 0,
    'No mention of a relation': 0,
    'Correlation': 1,
    'Causation': 2
}

CERTAINTY_LABEL_MAP = {
    'Somewhat uncertain': 0,
    'Uncertain': 0,
    'Somewhat certain': 1,
    'Certain': 2
}

GENERALIZATION_LABEL_MAP = {
    'Finding A': 0,
    'Finding B': 1,
    'They are at the same level of generality': 2
}

SENSATIONALISM_LABEL_MAP = LabelPassthrough()

TASK_ID_MAP = {
    'causality': CAUSAILTY_LABEL_MAP,
    'certainty': CERTAINTY_LABEL_MAP,
    'generalization': GENERALIZATION_LABEL_MAP,
    'sensationalism': SENSATIONALISM_LABEL_MAP
}


def preprocess_data(tk, examples):
    if 'text_pair' in examples:
        batch = tk(examples['text'], text_pair=examples['text_pair'], truncation=True)
    else:
        batch = tk(examples['text'], truncation=True)
    if 'label' in examples:
        batch['label'] = examples['label']

    return batch


def load_dataset_from_directory(dir, tokenizer, task='causality', use_regression=False):
    # Get the original spiced data
    spiced = load_dataset("copenlu/spiced", split="train+validation+test")

    # Load the train and test CSVs
    train_labs = pd.read_csv(f"{dir}/train.tsv", sep='\t')
    test_labs = pd.read_csv(f"{dir}/test.tsv", sep='\t')

    instances = set(pd.concat([train_labs, test_labs], axis=0)['id'])

    label_map = TASK_ID_MAP[task]

    instance_label_map = defaultdict(dict)

    if task != 'generalization':
        for j, row in pd.concat([train_labs, test_labs], axis=0).iterrows():
            instance_label_map[row['id']]['paper_label'] = label_map[row['label_paper_finding']]
            instance_label_map[row['id']]['reported_label'] = label_map[row['label_reported_finding']]
    else:
        for j, row in pd.concat([train_labs, test_labs], axis=0).iterrows():
            instance_label_map[row['id']]['label'] = label_map[row['agg_label']]

    dataset = spiced.filter(lambda example: example['instance_id'] in instances)

    # Create a dict
    dataset_dict = defaultdict(list)
    for example in dataset:
        if task != 'generalization':
            dataset_dict['id'].append(example['instance_id'])
            dataset_dict['text'].append(example['Paper Finding'])
            dataset_dict['label'].append(instance_label_map[example['instance_id']]['paper_label'])

            dataset_dict['id'].append(example['instance_id'])
            dataset_dict['text'].append(example['News Finding'])
            dataset_dict['label'].append(instance_label_map[example['instance_id']]['reported_label'])
        else:
            dataset_dict['id'].append(example['instance_id'])
            dataset_dict['text'].append(example['Paper Finding'])
            dataset_dict['text_pair'].append(example['News Finding'])
            dataset_dict['label'].append(instance_label_map[example['instance_id']]['label'])

    full_dataset = Dataset.from_dict(dataset_dict)
    if len(label_map) > 1:
        full_dataset = full_dataset.class_encode_column("label")

    train_val_dataset = full_dataset.filter(
        lambda example: example['id'] in set(train_labs['id'])) \
        .train_test_split(test_size=0.1, stratify_by_column='label' if len(label_map) > 1 else None)
    test_dataset = full_dataset.filter(lambda example: example['id'] in set(test_labs['id']))
    if use_regression:
        train_val_dataset = train_val_dataset.cast_column("label", Value("float32"))
        test_dataset = test_dataset.cast_column("label", Value("float32"))
    dataset = DatasetDict()
    dataset['train'] = train_val_dataset['train']
    dataset['validation'] = train_val_dataset['test']
    dataset['test'] = test_dataset

    column_names = test_dataset.column_names

    # Get the test IDs for error analysis
    testset = []
    reported = False
    for row in test_dataset:
        if task != 'generalization':
            if not reported:
                testset.append([f"{row['id']}_p", row['label']])
                reported = True
            else:
                testset.append([f"{row['id']}_r", row['label']])
                reported = False
        else:
            testset.append([f"{row['id']}", row['label']])

    return dataset.map(partial(preprocess_data, tokenizer), batched=True,
                       remove_columns=column_names), testset, label_map


def load_inference_dataset(data_jsonl, task='causality'):
    paper_dataset = defaultdict(list)
    news_dataset = defaultdict(list)
    tweet_dataset = defaultdict(list)

    original_data = []
    with open(data_jsonl) as f:
        for l in tqdm(f):
            data = json.loads(l)
            original_data.append(data)

            if task != 'generalization':
                # Load paper sentences
                for j, sentence in enumerate(data['paper_sentences']):
                    paper_dataset['article_id'].append(f"{data['doi']}_{j}")
                    paper_dataset['text'].append(sentence)

                # Load news sentences
                for news in data['news']:
                    if 'finding_sentences' in data['news'][news]:
                        for j, sentence in enumerate(data['news'][news]['finding_sentences']):
                            news_dataset['article_id'].append(f"{news}_{j}")
                            news_dataset['text'].append(sentence['text'])

                # Load tweets
                for j, tweet in enumerate(data['full_tweets']):
                    tdata = json.loads(tweet['tweet'])
                    tweet_dataset['article_id'].append(f"{data['doi']}_{j}")
                    tweet_dataset['text'].append(tdata['text'])
            else:
                # Load news sentences
                for news in data['news']:
                    if 'finding_sentences' in data['news'][news]:
                        for j, news_sentence in enumerate(data['news'][news]['finding_sentences']):
                            for k, paper_sentence in enumerate(data['paper_sentences']):
                                if news_sentence['paper_sentence_scores'][k] >= 3:
                                    news_dataset['article_id'].append(f"{news}_{j}_{k}")
                                    news_dataset['text'].append(
                                        {'text': paper_sentence, 'text_pair': news_sentence['text']})

                # Load tweets
                for j, tweet in enumerate(data['full_tweets']):
                    for k, paper_sentence in enumerate(data['paper_sentences']):
                        if tweet['paper_sentence_scores'][k] >= 3:
                            tdata = json.loads(tweet['tweet'])
                            tweet_dataset['article_id'].append(f"{data['doi']}_{j}_{k}")
                            tweet_dataset['text'].append({'text': paper_sentence, 'text_pair': tdata['text']})

    return Dataset.from_dict(paper_dataset), Dataset.from_dict(news_dataset), Dataset.from_dict(
        tweet_dataset), original_data
