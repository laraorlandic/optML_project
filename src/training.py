import torch
import torch.optim as optim

from src.models import CNN

# Global constants shared among all clients that we vary in testing
EPOCHS = 5
BATCH_SIZE = 50


class Client:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.batch_size = BATCH_SIZE
        self.epochs = EPOCHS
        self.lr = 0.001
        self.log_interval = 5
        self.seed = 42
        self.save_model = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = CNN().to(self.device)
        self.optimizer = optim.SGD(self.model.parameters(), lr=self.lr)
        self.gradient_compression = None
        self.criterion = torch.nn.CrossEntropyLoss()
        self.model_name = "mnist_cnn"


def train(client, epoch, logging=True):
    # put model in train mode, we need gradients
    client.model.train()
    train_loader = client.data_loader
    train_loss = 0
    for batch_idx, (data, target) in enumerate(train_loader):
        client.optimizer.zero_grad()
        output = client.model(data)
        # get the basic loss for our main task
        total_loss = client.criterion(output, target)
        total_loss.backward()
        train_loss += total_loss.item()
        client.optimizer.step()
    _, train_accuracy = test(client, logging=False)
    if logging:
        print(f'Train Epoch: {epoch} Loss: {total_loss.item():.6f}, Train accuracy: {train_accuracy}')
    return train_loss, train_accuracy


def test(client, logging=True):
    # put model in eval mode, disable dropout etc.
    client.model.eval()
    test_loss = 0
    correct = 0
    test_loader = client.data_loader
    # disable grad to perform testing quicker
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(client.device), target.to(client.device)
            output = client.model(data)
            test_loss += client.criterion(output, target).item()
            # prediction is an output with maximal probability
            pred = output.argmax(1, keepdim=True)
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)
    test_accuracy = 100. * correct / len(test_loader.dataset)
    if logging:
        print(f'Test set: Average loss: {test_loss:.4f}, '
              f'Test accuracy: {correct} / {len(test_loader.dataset)} '
              f'({test_accuracy:.0f}%)\n')
    return test_loss, test_accuracy


def average_client_models(clients):
    "Input list of clients, output a dictionary with their averaged parameters"
    dicts = []
    for client in clients:
        # TO-DO: Sparsify client paramters
        client_dict = dict(client.model.named_parameters())
        dicts.append(client_dict)
    dict_keys = dicts[0].keys()
    final_dict = dict.fromkeys(dict_keys)
    for key in dict_keys:
        # Average model parameters
        final_dict[key] = torch.cat([dictionary[key].unsqueeze(0) for dictionary in dicts], dim=0).sum(0).div(
            len(dicts))
    return final_dict