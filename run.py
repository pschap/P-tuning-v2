import logging
import os
import sys
import numpy as np
import pandas as pd
import torch
import random
from typing import Dict

import datasets
import transformers
from transformers import set_seed, Trainer
from transformers.trainer_utils import get_last_checkpoint

from arguments import get_args

from tasks.utils import *

os.environ["WANDB_DISABLED"] = "true"

logger = logging.getLogger(__name__)

def train(trainer, resume_from_checkpoint=None, last_checkpoint=None):
    checkpoint = None
    if resume_from_checkpoint is not None:
        checkpoint = resume_from_checkpoint
    elif last_checkpoint is not None:
        checkpoint = last_checkpoint
    train_result = trainer.train(resume_from_checkpoint=checkpoint)
    # trainer.save_model()

    metrics = train_result.metrics

    trainer.log_metrics("train", metrics)
    trainer.save_metrics("train", metrics)
    trainer.save_state()

    trainer.log_best_metrics()

def evaluate(trainer, resume_from_checkpoint=None):
    logger.info("*** Evaluate ***")

    if resume_from_checkpoint is not None:
        trainer._load_from_checkpoint(resume_from_checkpoint)

    logger.info("Model named parameters:")
    for name, param in trainer.model.named_parameters():
        if param.requires_grad:
            logger.info(f"\tName: {name}")
            logger.info(f"\tData: {param.data}")

    # Save evaluation metrics of non perturbed prompt vectors
    metrics = trainer.evaluate()

    trainer.log_metrics("eval", metrics)
    trainer.save_metrics("eval", metrics)

    # Permute prompt vectors
    avg_accuracy = 0.0
    eval_runs = 100
    prompts = trainer.model.prefix_encoder.embedding.weight
    for i in range(eval_runs):
        trainer.model.prefix_encoder.embedding.weight = torch.nn.Parameter(prompts[torch.randperm(prompts.size()[0])])
        metrics = trainer.evaluate()

        trainer.log_metrics(f"eval_permute_{i}", metrics)
        trainer.save_metrics("eval_permute_{i}", metrics)
        avg_accuracy += metrics["eval_accuracy"]

    avg_accuracy = avg_accuracy / eval_runs
    logger.info(f"Average permute accuracy: {avg_accuracy}")

    # Remove prompt vectors
    """ eval_runs = 5
    results = np.empty((1,15))
    results[:] = np.nan
    for j in range(15):
        avg_accuracy = 0.0
        for i in range(eval_runs):
            rows = random.sample(range(0, prompts.size()[0]), j)
            for r in rows:
                trainer.model.prefix_encoder.embedding.weight[r, :] = torch.nn.Parameter(torch.zeros(prompts.size()[1]))
            metrics = trainer.evaluate()

            trainer.log_metrics(f"eval_remove_{i}", metrics)
            trainer.save_metrics("eval_remove_{i}", metrics)
            avg_accuracy += metrics["eval_accuracy"]

        avg_accuracy = avg_accuracy / eval_runs
        logger.info(f"Average remove accuracy: {avg_accuracy}")
        results[0,j] = avg_accuracy
    df = pd.DataFrame(results, columns=[str(i) for i in range(15)])
    df = df.round(decimals=4)
    df.to_csv("remove_result.csv", index=False)  """

    # Remove first 7 prompt vectors
    trainer.model.prefix_encoder.embedding.weight[7, :] = torch.nn.Parameter(torch.zeros(7, prompts.size()[1]))
    metrics = trainer.evaluate()

    trainer.log_metrics("eval_remove_first", metrics)
    trainer.save_metrics("eval_remove_first", metrics)
    accuracy = metrics["eval_accuracy"]
    logger.info(f"Remove first 7 accuracy: {accuracy}")

    # Remove last 7 prompt vectors
    trainer.model.prefix_encoder.embedding.weight[57:64, :] = torch.nn.Parameter(torch.zeros(7, prompts.size()[1]))

    metrics = trainer.evaluate()

    trainer.log_metrics("eval_remove_first", metrics)
    trainer.save_metrics("eval_remove_first", metrics)
    accuracy = metrics["eval_accuracy"]
    logger.info(f"Remove last 7 accuracy: {accuracy}")

    # Remove middle 7 prompt vectors
    trainer.model.prefix_encoder.embedding.weight[28:35, :] = torch.nn.Parameter(torch.zeros(7, prompts.size()[1]))

    metrics = trainer.evaluate()

    trainer.log_metrics("eval_remove_first", metrics)
    trainer.save_metrics("eval_remove_first", metrics)
    accuracy = metrics["eval_accuracy"]
    logger.info(f"Remove middle 7 accuracy: {accuracy}")



    # Add noise to prompt vectors
    eval_runs = 5
    results = np.empty((1, 15))
    results[:] = np.nan
    for j in range(15):
        avg_accuracy = 0.0
        for i in range(eval_runs):
            rows = random.sample(range(0, prompts.size()[0]), j)
            for r in rows:
                trainer.model.prefix_encoder.embedding.weight[r, :] = torch.nn.Parameter(torch.randn(prompts.size()[1]))
            metrics = trainer.evaluate()

            trainer.log_metrics(f"eval_noise_{i}", metrics)
            trainer.save_metrics("eval_noise_{i}", metrics)
            avg_accuracy += metrics["eval_noise"]

        avg_accuracy = avg_accuracy / eval_runs
        logger.info(f"Average noise accuracy: {avg_accuracy}")
        results[0,j] = avg_accuracy

    df = pd.DataFrame(results, columns=[str(i) for i in range(15)])
    df = df.round(decimals=4)
    df.to_csv("remove_result.csv", index=False) 
        

def predict(trainer, predict_dataset=None):
    if predict_dataset is None:
        logger.info("No dataset is available for testing")

    elif isinstance(predict_dataset, dict):
        
        for dataset_name, d in predict_dataset.items():
            logger.info("*** Predict: %s ***" % dataset_name)
            predictions, labels, metrics = trainer.predict(d, metric_key_prefix="predict")
            predictions = np.argmax(predictions, axis=2)

            trainer.log_metrics("predict", metrics)
            trainer.save_metrics("predict", metrics)

    else:
        logger.info("*** Predict ***")
        predictions, labels, metrics = trainer.predict(predict_dataset, metric_key_prefix="predict")
        predictions = np.argmax(predictions, axis=2)

        trainer.log_metrics("predict", metrics)
        trainer.save_metrics("predict", metrics)

if __name__ == '__main__':

    args = get_args()

    _, data_args, training_args, _ = args

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    log_level = training_args.get_process_log_level()
    logger.setLevel(log_level)
    datasets.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()

    # Log on each process the small summary:
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        + f"distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16}"
    )
    logger.info(f"Training/evaluation parameters {training_args}")
    

    if not os.path.isdir("checkpoints") or not os.path.exists("checkpoints"):
        os.mkdir("checkpoints")

    if data_args.task_name.lower() == "superglue":
        assert data_args.dataset_name.lower() in SUPERGLUE_DATASETS
        from tasks.superglue.get_trainer import get_trainer

    elif data_args.task_name.lower() == "glue":
        assert data_args.dataset_name.lower() in GLUE_DATASETS
        from tasks.glue.get_trainer import get_trainer

    elif data_args.task_name.lower() == "ner":
        assert data_args.dataset_name.lower() in NER_DATASETS
        from tasks.ner.get_trainer import get_trainer

    elif data_args.task_name.lower() == "srl":
        assert data_args.dataset_name.lower() in SRL_DATASETS
        from tasks.srl.get_trainer import get_trainer
    
    elif data_args.task_name.lower() == "qa":
        assert data_args.dataset_name.lower() in QA_DATASETS
        from tasks.qa.get_trainer import get_trainer
        
    else:
        raise NotImplementedError('Task {} is not implemented. Please choose a task from: {}'.format(data_args.task_name, ", ".join(TASKS)))

    set_seed(training_args.seed)

    trainer, predict_dataset = get_trainer(args)

    last_checkpoint = None
    if os.path.isdir(training_args.output_dir) and training_args.do_train and not training_args.overwrite_output_dir:
        last_checkpoint = get_last_checkpoint(training_args.output_dir)
        if last_checkpoint is None and len(os.listdir(training_args.output_dir)) > 0:
            raise ValueError(
                f"Output directory ({training_args.output_dir}) already exists and is not empty. "
                "Use --overwrite_output_dir to overcome."
            )
        elif last_checkpoint is not None and training_args.resume_from_checkpoint is None:
            logger.info(
                f"Checkpoint detected, resuming training at {last_checkpoint}. To avoid this behavior, change "
                "the `--output_dir` or add `--overwrite_output_dir` to train from scratch."
            )


    # if training_args.do_train:
    #     train(trainer, training_args.resume_from_checkpoint, last_checkpoint)
    
    if training_args.do_eval:
        evaluate(trainer, last_checkpoint)

    # if training_args.do_predict:
    #     predict(trainer, predict_dataset)

   
