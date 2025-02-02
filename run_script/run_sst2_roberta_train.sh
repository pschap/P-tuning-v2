#!/bin/bash

#SBATCH --account=PAS2318
#SBATCH --time 50:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=20
#SBATCH --gpus-per-node=1

export TASK_NAME=glue
export DATASET_NAME=sst2
export CUDA_VISIBLE_DEVICES=0

bs=32
lr=5e-3
dropout=0.1
psl=64
epoch=50

python3 run.py \
  --model_name_or_path roberta-large \
  --task_name $TASK_NAME \
  --dataset_name $DATASET_NAME \
  --do_train \
  --max_seq_length 128 \
  --per_device_train_batch_size $bs \
  --learning_rate $lr \
  --num_train_epochs $epoch \
  --pre_seq_len $psl \
  --output_dir checkpoints/$DATASET_NAME-roberta/ \
  --overwrite_output_dir \
  --hidden_dropout_prob $dropout \
  --seed 11 \
  --save_strategy no \
  --evaluation_strategy epoch \
  --prefix
  