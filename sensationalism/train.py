import argparse
import json
import os
import random

import evaluate
import numpy as np
import pandas as pd
import torch
import wandb
from sklearn.metrics import classification_report
from transformers import AutoTokenizer, AutoConfig, AutoModelForSequenceClassification
from transformers import TrainingArguments, Trainer

from util.datareader import LabelPassthrough
from util.datareader import TASK_ID_MAP
from util.datareader import load_dataset_from_directory
from util.trainer import WeightedTrainer


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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", help="Location of the data", required=True, type=str)
    parser.add_argument("--cache_dir", help="Local cache for models and tokenizers", default=None, type=str)
    parser.add_argument("--model", help="Model ID to use", default="roberta-base", type=str)
    parser.add_argument("--task", help="Which task to train on", default="causality", choices=list(TASK_ID_MAP.keys()),
                        type=str)
    parser.add_argument("--seed", type=int, help="Random seed", default=1000)
    parser.add_argument("--output_dir", help="Top level directory to save the models", required=True, type=str)

    parser.add_argument("--run_name", help="A name for this run", required=True, type=str)
    parser.add_argument("--batch_size", help="The batch size", type=int, default=8)
    parser.add_argument("--learning_rate", help="The learning rate", type=float, default=2e-5)
    parser.add_argument("--weight_decay", help="Amount of weight decay", type=float, default=0.0)
    parser.add_argument("--dropout_prob", help="The dropout probability", type=float, default=0.1)
    parser.add_argument("--n_epochs", help="The number of epochs to run", type=int, default=2)
    parser.add_argument("--use_class_weight", help="Whether to use balanced class weights", action="store_true")
    parser.add_argument("--use_regression", help="Just treat the problem as regression", action="store_true")
    parser.add_argument("--n_gpu", help="The number of gpus to use", type=int, default=1)
    parser.add_argument("--warmup_steps", help="The number of warmup steps", type=int, default=200)
    parser.add_argument("--tags", help="Tags to pass to wandb", required=False, type=str, default=[], nargs='+')
    parser.add_argument("--metrics_dir", help="Directory to store metrics for making latex tables", required=True,
                        type=str)
    parser.add_argument("--predictions_savefile", help="Where to save the predictions to", default=None,
                        type=str)

    args = parser.parse_args()

    seed = args.seed
    weight_decay = args.weight_decay
    n_epochs = args.n_epochs
    batch_size = args.batch_size
    n_labels = max(TASK_ID_MAP[args.task].values()) + 1 if not args.use_regression else 1
    use_class_weight = args.use_class_weight
    if not os.path.exists(f"{args.output_dir}"):
        os.makedirs(f"{args.output_dir}")
    if not os.path.exists(f"{args.metrics_dir}"):
        os.makedirs(f"{args.metrics_dir}")

    device = torch.device('cpu')
    if torch.cuda.is_available():
        print("Using CUDA")
        device = torch.device('cuda')

    # Enforce reproducibility
    # Always first
    enforce_reproducibility(seed)
    config = {
        'run_name': args.run_name,
        'seed': seed,
        'model_name': args.model,
        'output_dir': args.output_dir,
        'tags': args.tags,
        'batch_size': args.batch_size,
        'learning_rate': args.learning_rate,
        'weight_decay': args.weight_decay,
        'warmup_steps': args.warmup_steps,
        'epochs': args.n_epochs,
        'seed': args.seed,
        'task': args.task,
        'use_class_weight': use_class_weight
    }

    run = wandb.init(
        name=args.run_name,
        config=config,
        reinit=True,
        tags=args.tags
    )

    tk = AutoTokenizer.from_pretrained(args.model, cache_dir=args.cache_dir)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        do_train=True,
        do_eval=True,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        num_train_epochs=args.n_epochs,
        warmup_steps=args.warmup_steps,
        seed=seed,
        load_best_model_at_end=True
    )

    dataset, testset, label_map = load_dataset_from_directory(
        args.data,
        tk,
        task=args.task,
        use_regression=args.use_regression
    )

    if args.task != 'sensationalism':
        reverse_labelmap = {v: k for k, v in label_map.items()}
    else:
        reverse_labelmap = LabelPassthrough()

    if n_labels > 1:
        metric = evaluate.load("f1", average='macro')
    else:
        metric = evaluate.load("pearsonr")


    def compute_metrics(eval_pred):
        preds, labels = eval_pred
        if n_labels > 1:
            predictions = preds.argmax(-1)
            return metric.compute(predictions=predictions, references=labels, average='macro')
        else:
            predictions = preds
            return metric.compute(predictions=predictions, references=labels)


    config = AutoConfig.from_pretrained(args.model, num_labels=n_labels)
    model = AutoModelForSequenceClassification.from_pretrained(args.model, config=config)

    if n_labels > 1 and use_class_weight:
        labels = np.array(dataset['train']['label'])
        class_weight = torch.tensor(len(labels) / (n_labels * np.bincount(labels)))
        class_weight = class_weight.type(torch.FloatTensor).to(device)
        print(class_weight)
        trainer = WeightedTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset['train'],
            eval_dataset=dataset['validation'],
            compute_metrics=compute_metrics,
            tokenizer=tk,
            class_weight=class_weight
        )
    else:
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset['train'],
            eval_dataset=dataset['validation'],
            compute_metrics=compute_metrics,
            tokenizer=tk
        )

    trainer.train()

    # Delete old checkpoints and save best model
    # shutil.rmtree(args.output_dir)
    # os.makedirs(f"{args.output_dir}")
    trainer.model.save_pretrained(f"{args.output_dir}/{seed}")
    tk.save_pretrained(f"{args.output_dir}/{seed}")

    met_preds = trainer.predict(dataset['test'])
    metrics = met_preds.metrics
    predictions = met_preds.predictions

    if args.predictions_savefile is not None:
        predictions_dframe = []
        for test, pred in zip(testset, predictions):
            if args.task != 'sensationalism':
                predictions_dframe.append([test[0], reverse_labelmap[test[1]], reverse_labelmap[np.argmax(pred, -1)]])
            else:
                predictions_dframe.append([test[0], reverse_labelmap[test[1]], pred[0]])

        predictions_dframe = pd.DataFrame(predictions_dframe, columns=["id", "label", "pred"])
        predictions_dframe.to_csv(args.predictions_savefile, sep='\t', index=None)
    with open(f"{args.metrics_dir}/{seed}.jsonl", 'wt') as f:
        f.write(json.dumps(metrics))
    wandb.log(metrics)
    if n_labels > 1:
        print(classification_report(np.array(dataset['test']['label']), np.argmax(predictions, -1)))
