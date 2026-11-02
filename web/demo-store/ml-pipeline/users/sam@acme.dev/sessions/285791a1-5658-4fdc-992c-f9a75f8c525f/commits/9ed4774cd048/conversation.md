# Conversation behind 9ed4774cd048: Clip gradients at 1.0

### Tool result

```
[main 60e503f] Lower LR and lengthen warmup to stop divergence
```

## User

Add gradient clipping too, as a safety net.

### Assistant (thinking)

run-19 is stable but grad_norm briefly hit 6.0 near step 700. Clip at 1.0 is the usual choice for LoRA; 0.3 slowed learning in run-12 last week.

### Tool call: `Edit`

```
{
 "file_path": "/home/dev/code/ml-pipeline/train.py",
 "old_string": "GRAD_CLIP = None",
 "new_string": "GRAD_CLIP = 1.0"
}
```

### Tool result

```
The file train.py has been updated.
```

### Tool call: `Bash`

```
{
 "command": "python train.py --run run-20",
 "description": ""
}
```

### Tool result

```
step 1000 loss 1.78 grad_norm 0.7 clipped 3x
eval_loss 1.81
DONE
```

## Assistant

Added clipping at 1.0. run-20: eval loss 1.81, clipping fired 3 times.

### Tool call: `Bash`

```
{
 "command": "git commit -am \"Clip gradients at 1.0\"",
 "description": "Commit"
}
```
