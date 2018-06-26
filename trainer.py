import torch


import cfgs.config as cfg  # make a common config file
import os
import sys


import utils.network as net_utils  # THEY HAVE ALTERNATES

import datetime
from darknet import Darknet19 as Darknet
from utils.timer import Timer
from random import randint


import torchvision
import argparse

try:
    from tensorboardX import SummaryWriter
except ImportError:
    SummaryWriter = None

from dataset import dataset as dset
import time


def arg_parse():
    """
    Parse arguements to the training module

    """

    parser = argparse.ArgumentParser(description='Training module')

    parser.add_argument("-i", dest='images', help="path to train image directory",
                        default="imgs", type=str)
    parser.add_argument("-w", dest='workers', help="number of workers to load the images",
                        default="4", type=int)
    parser.add_argument("-b", dest="batch", help="Batch size", default=30, type=int)

    parser.add_argument("-tl", dest='transfer', help='transfer_learning', default=False, type=bool)

    parser.add_argument("-c", dest='cfgfile', help="Config file",
                        default="cfg/yolov3.cfg", type=str)
    parser.add_argument("-t", dest="use_tensorboard", help="Disable tensorboard", default=True, type=bool)

    return parser.parse_args()


if __name__ == '__main__':

    args = arg_parse()
    lmdb = 1

    # Use LMDB or not
    if cfg.lmdb:
        dataset = dset(cfg.target_file, cfg.root_dir, cfg.multi_scale_inp_size)  # , cfg.transforms)
        dataloader = torch.utils.data.DataLoader(dataset, batch_size=args.batch, shuffle=True, num_workers=args.workers)

    else:

        image_data = torchvision.datasets.ImageFolder(args.path)
        data_loader = torch.utils.data.DataLoader(image_data, batch_size=args.batch, shuffle=True, num_workers=args.workers, multiscale=cfg.multi_scale_inp_size)

    classes = 20 if args.transfer else 4
    net = Darknet(classes)

    # load from a checkpoint
    if args.transfer:
        net.load_from_npz(cfg.pretrained_model, num_conv=18)
        exp_name = str(int(time.time()))  # For tensorboard consistency on reloads
        start_epoch = 0
        j = 0
        lr = cfg.init_learning_rate

    else:
        path_t = cfg.trained_model()
        if os.path.exists(path_t):
            j, exp_name, start_epoch, lr = net_utils.load_net(path_t, net)
            j, exp_name, start_epoch, lr = int(j), str(int(exp_name)), int(start_epoch), float(lr)
            print('lr is {} and its type is {}'.format(lr, type(lr)))
        else:
            e = 'no checkpoint to load from\n'
            sys.exit(e)

    path = os.path.join(cfg.TRAIN_DIR, 'runs', str(exp_name))
    if not os.path.exists(path):
        os.makedirs(path)

    if args.transfer:
        for params in net.parameters():
            params.requires_grad = False
        shape = net.conv5.conv.weight.shape
        new_layer = net_utils.Conv2d(shape[1], 45, shape[2], 1, relu=False)
        net.conv5 = new_layer  # make it generalizable

        print('Tranfer Learning Active')

    # os.environ['CUDA_VISIBLE_DEVICES'] = 0, 1, 2
    # torch.cuda.manual_seed(seed)
    # net = torch.nn.DataParallel(net).cuda()
    net.train()

    print('network loaded')

    # Optimizer

    optimizable = net.conv5.parameters  # this is always the case whether transfer or not
    net.cuda()
    # net = torch.nn.DataParallel(net)

    # net = torch.nn.DataParallel(net, device_sids=list(range(torch.cuda.device_count())))

    optimizer = torch.optim.SGD(optimizable(), lr=lr, momentum=cfg.momentum, weight_decay=cfg.weight_decay)
    print('this')
    # tensorboard
    if args.use_tensorboard and SummaryWriter is not None:
        summary_writer = SummaryWriter(path)

    batch_per_epoch = dataset.length / args.batch
    train_loss = 0
    bbox_loss, iou_loss, cls_loss = 0., 0., 0.
    cnt = 0
    step_cnt = 0
    size_index = 0
    t = Timer()
    epoch = start_epoch
    print('this')
    for step in range(int(epoch), cfg.max_epoch):

        # batch
        for i, batch_of_index in enumerate(dataloader):
            t.tic()

            # OG yolo changes scales every 10 epochs
            if i % 10 == 0:
                size_index = randint(0, len(cfg.multi_scale_inp_size) - 1)
                print('new scale is {}'.format(cfg.multi_scale_inp_size[size_index]))

            batch = dataset.fetch_parse(batch_of_index, size_index)
            im = batch['images']
            gt_boxes = batch['gt_boxes']
            gt_classes = batch['gt_classes']
            dontcare = batch['dontcare']
            origin_im = ['origin_im']

            im = net_utils.np_to_variable(im,
                                          is_cuda=True,
                                          volatile=False).permute(0, 3, 1, 2)

            bbox_pred, iou_pred, prob_pred = net(im, gt_boxes=gt_boxes, gt_classes=gt_classes, dontcare=dontcare, size_index=size_index)

            loss = net.loss
            bbox_loss += net.bbox_loss.data.cpu().numpy()[0]
            iou_loss += net.iou_loss.data.cpu().numpy()[0]
            cls_loss += net.cls_loss.data.cpu().numpy()[0]

            train_loss += loss.data.cpu().numpy()[0]
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            cnt += 1
            step_cnt += 1
            j += 1
            duration = t.toc()

            if cnt % cfg.disp_interval == 0:

                train_loss /= cnt
                bbox_loss /= cnt
                iou_loss /= cnt
                cls_loss /= cnt

                print(('epoch %d[%d/%d], loss: %.3f, bbox_loss: %.3f, iou_loss: %.3f, '
                       'cls_loss: %.3f (%.2f s/batch, rest:%s)' %
                       (step, step_cnt, batch_per_epoch, train_loss, bbox_loss,
                        iou_loss, cls_loss, duration,
                        str(datetime.timedelta(seconds=int((batch_per_epoch - step_cnt) * duration))))))

                summary_writer.add_scalar('loss_train', train_loss, j)
                summary_writer.add_scalar('loss_bbox', bbox_loss, j)
                summary_writer.add_scalar('loss_iou', iou_loss, j)
                summary_writer.add_scalar('loss_cls', cls_loss, j)
                summary_writer.add_scalar('learning_rate', lr, j)

                train_loss = 0
                bbox_loss, iou_loss, cls_loss = 0., 0., 0.
                cnt = 0
                t.clear()

        if step % cfg.lr_decay_epochs == 1:
            lr *= cfg.lr_decay
            optimizer = torch.optim.SGD(optimizable(), lr=lr, momentum=cfg.momentum, weight_decay=cfg.weight_decay)

        train_output_dir = os.path.join(cfg.TRAIN_DIR, 'checkpoints', exp_name)
        cfg.mkdir(train_output_dir, max_depth=3)
        save_name = os.path.join(train_output_dir, '{}.h5'.format(step))
        net_utils.save_net(j, exp_name, step + 1, lr, save_name, net)
        print(('save model: {}'.format(save_name)))

        if step % 10 == 1:
            cfg.clean_ckpts(train_output_dir)

        step_cnt = 0
