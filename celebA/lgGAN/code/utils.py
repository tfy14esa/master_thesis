"""
Some codes from https://github.com/Newmu/dcgan_code
"""
from __future__ import division
import math
import json
import random
import pprint
import scipy.misc
import numpy as np
import scipy.io as sio
from time import gmtime, strftime
from six.moves import xrange
import os

import tensorflow as tf
import tensorflow.contrib.slim as slim

pp = pprint.PrettyPrinter()


def get_stddev(x, k_h, k_w): return 1 / \
    math.sqrt(k_w * k_h * x.get_shape()[-1])


def show_all_variables():
    model_vars = tf.trainable_variables()
    slim.model_analyzer.analyze_vars(model_vars, print_info=True)

def get_image_interpolate(image_path, input_height, input_width,
              resize_height=128, resize_width=128,
              crop=True, grayscale=False, alpha = 1.0):
    image = imread(image_path, grayscale)
    im1 = transform(image, input_height, input_width,
                     resize_height, resize_width, crop)
    if crop:
        cropped_image = center_crop(
            image, input_height, input_width,
            int(resize_height/2), int(resize_width/2))
    else:
        cropped_image = scipy.misc.imresize(
            image, [int(resize_height/2), int(resize_width/2)])
    im2 = scipy.misc.imresize(
            cropped_image, [resize_height, resize_width], interp = 'nearest')
    im2 = np.array(im2) / 127.5 - 1.

    return im2*(1-alpha)+im1*alpha

def get_image(image_path, input_height, input_width,
              resize_height=128, resize_width=128,
              crop=True, grayscale=False):
    image = imread(image_path, grayscale)
    return transform(image, input_height, input_width,
                     resize_height, resize_width, crop)


def save_images(images, size, image_path):
    return imsave(inverse_transform(images), size, image_path)


def imread(path, grayscale=False):
    if (grayscale):
        return scipy.misc.imread(path, flatten=True).astype(np.float)
    else:
        return scipy.misc.imread(path).astype(np.float)


def merge_images(images, size):
    return inverse_transform(images)


def merge(images, size):
    h, w = images.shape[1], images.shape[2]
    if (images.shape[3] in (3, 4)):
        c = images.shape[3]
        img = np.zeros((h * size[0], w * size[1], c))
        for idx, image in enumerate(images):
            i = idx % size[1]
            j = idx // size[1]
            img[j * h:j * h + h, i * w:i * w + w, :] = image
        return img
    elif images.shape[3] == 1:
        img = np.zeros((h * size[0], w * size[1]))
        for idx, image in enumerate(images):
            i = idx % size[1]
            j = idx // size[1]
            img[j * h:j * h + h, i * w:i * w + w] = image[:, :, 0]
        return img
    else:
        raise ValueError('in merge(images,size) images parameter '
                         'must have dimensions: HxW or HxWx3 or HxWx4')


def imsave(images, size, path):
    image = np.squeeze(merge(images, size))
    return scipy.misc.imsave(path, image)


def center_crop(x, crop_h, crop_w,
                resize_h=128, resize_w=128):
    if crop_w is None:
        crop_w = crop_h
    h, w = x.shape[:2]
    j = int(round((h - crop_h) / 2.))
    i = int(round((w - crop_w) / 2.))
    return scipy.misc.imresize(
        x[j:j + crop_h, i:i + crop_w], [resize_h, resize_w])


def transform(image, input_height, input_width,
              resize_height=128, resize_width=128, crop=True):
    if crop:
        cropped_image = center_crop(
            image, input_height, input_width,
            resize_height, resize_width)
    else:
        cropped_image = scipy.misc.imresize(
            image, [resize_height, resize_width])
    return np.array(cropped_image) / 127.5 - 1.


def inverse_transform(images):
    return (images + 1.) / 2.

def dir_name(flags):
    return "Arch{}_Zd{}_L{}_Bs{}_Lr{}_Zd{}_Iwh{}_Owh{}".format(
        flags.architecture, flags.z_dim, flags.loss, flags.batch_size, flags.learning_rate, flags.zdistribution,
        flags.input_height, flags.output_width)


def visualize(sess, gan, config):
    image_frame_dim_h = 8
    image_frame_dim_w = 8

    for idx in xrange(100):
        print(" [*] %d" % idx)
        z_sample = np.random.uniform(-1, 1, size=(gan.sample_num, gan.z_dim))
        samples = sess.run(gan.sampler, feed_dict={gan.z: z_sample})

        if not os.path.exists('../test_samples/' + dir_name(config)):
            os.makedirs('../test_samples/' + dir_name(config))
        save_images(samples, [image_frame_dim_h, image_frame_dim_w],
                    '../test_samples/' + dir_name(config) + '/test_arange_%s.png' % (idx))


# def image_manifold_size(num_images):
#     manifold_h = 8
#     manifold_w = 8
#     assert manifold_h * manifold_w == num_images
#     return manifold_h, manifold_w
