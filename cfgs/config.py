import os
from .config_voc import *  # noqa
from .exps.darknet19_exp1 import *  # noqa
import glob


# creates non existing directories
def mkdir(path, max_depth=3):
    parent, child = os.path.split(path)
    if not os.path.exists(parent) and max_depth > 1:
        os.mkdir(parent, max_depth - 1)

    if not os.path.exists(path):
        os.mkdir(path)


# input and output size
############################


multi_scale_inp_size = [np.array([320, 320], dtype=np.int),
                        np.array([352, 352], dtype=np.int),
                        np.array([384, 384], dtype=np.int),
                        np.array([416, 416], dtype=np.int),
                        np.array([448, 448], dtype=np.int),
                        np.array([480, 480], dtype=np.int),
                        np.array([512, 512], dtype=np.int),
                        np.array([544, 544], dtype=np.int),
                        np.array([576, 576], dtype=np.int),
                        # np.array([608, 608], dtype=np.int),
                        ]   # w, h
multi_scale_out_size = [multi_scale_inp_size[0] / 32,
                        multi_scale_inp_size[1] / 32,
                        multi_scale_inp_size[2] / 32,
                        multi_scale_inp_size[3] / 32,
                        multi_scale_inp_size[4] / 32,
                        multi_scale_inp_size[5] / 32,
                        multi_scale_inp_size[6] / 32,
                        multi_scale_inp_size[7] / 32,
                        multi_scale_inp_size[8] / 32,
                        # multi_scale_inp_size[9] / 32,
                        ]   # w, h
inp_size = np.array([416, 416], dtype=np.int)   # w, h
out_size = inp_size / 32


# for display
############################
def _to_color(indx, base):
    """ return (b, r, g) tuple"""
    base2 = base * base
    b = 2 - indx / base2
    r = 2 - (indx % base2) / base
    g = 2 - (indx % base2) % base
    return b * 127, r * 127, g * 127


base = int(np.ceil(pow(num_classes, 1. / 3)))
colors = [_to_color(x, base) for x in range(num_classes)]


# detection config
############################
thresh = 0.3


# dir config
############################
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(ROOT_DIR, 'db')
MODEL_DIR = os.path.join(ROOT_DIR, 'models')
TRAIN_DIR = os.path.join(MODEL_DIR, 'training')
TEST_DIR = os.path.join(MODEL_DIR, 'testing')

root_dir = os.path.join(DATA_DIR, 'image_data')
target_file = glob.glob(os.path.join(DATA_DIR, 'targets', '*.json'))[0]
transforms = False

# gets the latest file from the latest experiment and returns its abs path


def trained_model():
    exp_name = str(sorted([int(i.split('/')[-1]) for i in glob.glob(os.path.join(TRAIN_DIR, 'checkpoints', '*'))])[-1])
    trained_model = glob.glob(os.path.join(TRAIN_DIR, 'checkpoints', exp_name, '*.h5'))
    split_key = []
    split_dict = {}
    for elements in trained_model:
        jamba = int((elements.split('/')[-1]).split('.')[0])
        split_key.append(jamba)
        split_dict[jamba] = elements

    return split_dict[sorted(split_key)[-1]]


# Cleans all checkpoint except latest n no, n =  remain
def clean_ckpts(train_dir):
    remain = 4
    ckpts = dict(map(lambda x: (int(x.split('/')[-1].split('.')[0]), x), glob.glob(os.path.join(train_dir, '*'))))
    samba = sorted(ckpts.keys())
    samba = samba[:(len(samba) - remain)]
    for key in samba:
        os.remove(ckpts[key])
    # just to ensure we hit the jackpot
    print('remaining checkpoints are {}'.format(map(lambda x: x.split('/')[-1], glob.glob(os.path.join(train_dir, '*')))))


# get the pretrained model(The one we apply transfer learning on)
pretrained_model = glob.glob(os.path.join(MODEL_DIR, '*.npz'))[0]


rand_seed = 1024
use_tensorboard = True

log_interval = 10
disp_interval = 10

lmdb = 1
