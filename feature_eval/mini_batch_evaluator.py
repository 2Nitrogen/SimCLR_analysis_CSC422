import torch
import sys
import numpy as np
import os
import yaml
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader
import torchvision
import torchvision.transforms as transforms
from torchvision import datasets
import torch
import torch.version

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print("Using device:", device)

with open(os.path.join('./config.yml')) as file:
#   print( file )
    config = yaml.load(file, Loader=yaml.FullLoader)

# Load trained model
path = os.path.expanduser( '~/SimCLR/runs/Apr13_14-18-24_j-leelab1.mae.ncsu.edu/checkpoint_0200.pth.tar' )
checkpoint = torch.load(path, map_location=device)
state_dict = checkpoint['state_dict']

######

def get_stl10_data_loaders(download, shuffle=False, batch_size=256):
    dataset_path = os.path.expanduser( '~/SimCLR/datasets' )

    train_dataset = datasets.STL10(dataset_path, split='train', download=download,
                                  transform=transforms.ToTensor())

    train_loader = DataLoader(train_dataset, batch_size=batch_size,
                            num_workers=0, drop_last=False, shuffle=shuffle)
  
    test_dataset = datasets.STL10(dataset_path, split='test', download=download,
                                  transform=transforms.ToTensor())

    test_loader = DataLoader(test_dataset, batch_size=2*batch_size,
                            num_workers=10, drop_last=False, shuffle=shuffle)
    return train_loader, test_loader

def get_cifar10_data_loaders(download, shuffle=False, batch_size=256):
    train_dataset = datasets.CIFAR10('./data', train=True, download=download,
                                  transform=transforms.ToTensor())

    train_loader = DataLoader(train_dataset, batch_size=batch_size,
                            num_workers=0, drop_last=False, shuffle=shuffle)
  
    test_dataset = datasets.CIFAR10('./data', train=False, download=download,
                                  transform=transforms.ToTensor())

    test_loader = DataLoader(test_dataset, batch_size=2*batch_size,
                            num_workers=10, drop_last=False, shuffle=shuffle)
    return train_loader, test_loader

def accuracy(output, target, topk=(1,)):
    """Computes the accuracy over the k top predictions for the specified values of k"""
    with torch.no_grad():
        maxk = max(topk)
        batch_size = target.size(0)

        _, pred = output.topk(maxk, 1, True, True)
        pred = pred.t()
        correct = pred.eq(target.view(1, -1).expand_as(pred))

        res = []
        for k in topk:
            correct_k = correct[:k].reshape(-1).float().sum(0, keepdim=True)
            res.append(correct_k.mul_(100.0 / batch_size))
        return res

######

if config['arch'] == 'resnet18':
    model = torchvision.models.resnet18(pretrained=False, num_classes=10).to(device)
elif config['arch'] == 'resnet50':
    model = torchvision.models.resnet50(pretrained=False, num_classes=10).to(device)

for k in list(state_dict.keys()):
    if (k.startswith('backbone.')) and (not k.startswith('backbone.fc')):
        # remove prefix
        state_dict[k[len("backbone."):]] = state_dict[k]
    del state_dict[k]

log = model.load_state_dict(state_dict, strict=False)
assert log.missing_keys == ['fc.weight', 'fc.bias']

if config['dataset_name'] == 'cifar10':
    train_loader, test_loader = get_cifar10_data_loaders(download=True)
elif config['dataset_name'] == 'stl10':
    train_loader, test_loader = get_stl10_data_loaders(download=False) # Because I've already downloaded STL10 dataset
print("Dataset:", config['dataset_name'])

# freeze all layers but the last fc
for name, param in model.named_parameters():
    if name not in ['fc.weight', 'fc.bias']:
        param.requires_grad = False

# parameters = list(filter(lambda p: p.requires_grad, model.parameters()))
# assert len(parameters) == 2  # fc.weight, fc.bias

optimizer = torch.optim.Adam(model.parameters(), lr=3e-4, weight_decay=0.0008)
criterion = torch.nn.CrossEntropyLoss().to(device)


epochs = 100
for epoch in range(epochs):
    top1_train_accuracy = 0
    for counter, (x_batch, y_batch) in enumerate(train_loader):
        x_batch = x_batch.to(device)
        y_batch = y_batch.to(device)

        logits = model(x_batch)
        loss = criterion(logits, y_batch)
        top1 = accuracy(logits, y_batch, topk=(1,))
        top1_train_accuracy += top1[0]

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    top1_train_accuracy /= (counter + 1)
    top1_accuracy = 0
    top5_accuracy = 0
    for counter, (x_batch, y_batch) in enumerate(test_loader):
        x_batch = x_batch.to(device)
        y_batch = y_batch.to(device)

        logits = model(x_batch)
  
        top1, top5 = accuracy(logits, y_batch, topk=(1,5))
        top1_accuracy += top1[0]
        top5_accuracy += top5[0]
  
    top1_accuracy /= (counter + 1)
    top5_accuracy /= (counter + 1)
    print(f"Epoch {epoch}\tTop1 Train accuracy {top1_train_accuracy.item()}\tTop1 Test accuracy: {top1_accuracy.item()}\tTop5 test acc: {top5_accuracy.item()}")