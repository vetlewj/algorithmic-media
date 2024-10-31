#!/bin/bash

# One seed for now
for i in 1000,1 1001,2 666,3 7,4 50,5; do IFS=","; set -- $i;
  task='causality'
  python train.py \
    --run_name ${task} \
    --seed ${1} \
    --data data/annotations/${task}-mace/ \
    --output_dir output/${task}/ \
    --metrics_dir metrics/${task}/ \
    --n_epochs 5 \
    --task ${task} \
    --tags ${task} \
    --model allenai/scibert_scivocab_uncased \
    --weight_decay 0.01 \
    --predictions_savefile predictions/${task}_scibert_seed${seed}.tsv

  task='certainty'
  python train.py \
    --run_name ${task} \
    --seed ${1} \
    --data data/annotations/${task}-mace/ \
    --output_dir output/${task}/ \
    --metrics_dir metrics/${task}/ \
    --n_epochs 5 \
    --task ${task} \
    --tags ${task} \
    --model allenai/scibert_scivocab_uncased \
    --weight_decay 0.01 \
    --predictions_savefile predictions/${task}_scibert_seed${seed}.tsv

  task='generalization'
  python train.py \
    --run_name ${task} \
    --seed ${1} \
    --data data/annotations/${task}-mace/ \
    --output_dir output/${task}/ \
    --metrics_dir metrics/${task}/ \
    --n_epochs 5 \
    --task ${task} \
    --tags ${task} \
    --model allenai/scibert_scivocab_uncased \
    --weight_decay 0.01 \
    --use_class_weight \
    --predictions_savefile predictions/${task}_scibert_seed${seed}.tsv


  task='sensationalism'
  python train.py \
      --run_name ${task} \
      --seed ${1} \
      --data data/annotations/${task}-mace/ \
      --output_dir output/${task}/ \
      --metrics_dir metrics/${task}/ \
      --n_epochs 5 \
      --task ${task} \
      --tags ${task} \
      --model roberta-base \
      --weight_decay 0.01 \
      --predictions_savefile predictions/${task}_roberta_seed${seed}.tsv

done