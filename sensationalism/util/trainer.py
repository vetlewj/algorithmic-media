from torch import nn
from transformers import Trainer


class WeightedTrainer(Trainer):
    def __init__(self, *args, **kwargs):
        self.class_weight = kwargs.pop('class_weight')
        super().__init__(*args, **kwargs)

    def compute_loss(self, model, inputs, return_outputs=False):
        labels = inputs.pop("labels")
        # forward pass
        outputs = model(**inputs)
        logits = outputs.get("logits")
        # compute custom loss (suppose one has 3 labels with different weights)
        loss_fct = nn.CrossEntropyLoss(weight=self.class_weight)
        loss = loss_fct(logits, labels.view(-1))
        return (loss, outputs) if return_outputs else loss
