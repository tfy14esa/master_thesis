from __future__ import division
import os
import time
import math
from glob import glob
import scipy.io as sio
import tensorflow as tf
import numpy as np
from six.moves import xrange

from model import *
from ops import *
from utils import *

import matplotlib
matplotlib.use('agg')
from matplotlib import cm, pyplot as plt

class subGAN(object):
	def __init__(
		self,
		sess,
		z_dim,
		epochs,
		g_layers,
		d_layers,
		useAlpha,
		useBeta,
		useGamma,
		useTau,
		feature_map_shrink,
		feature_map_growth,
		spatial_map_shrink,
		spatial_map_growth,
		stage,
		loss,
		z_distr,
		activation,
		weight_init,  # NOT TAKEN CARE OF
		lr,
		beta1,
		beta2,
		epsilon,
		batch_size,
		sample_num,
		input_size,
		output_size,
		g_batchnorm,
		d_batchnorm,
		normalize_z,
		crop,
		visualize,  # NOT TAKEN CARE OF
		model_dir,
		minibatch_std,
		use_wscale, 
		use_pixnorm,
		D_loss_extra,
		G_run_avg, # NOT TAKEN CARE OF
		oldSpecs):

		self.sess = sess
		self.z_dim = z_dim
		self.epochs = epochs
		self.g_layers = g_layers
		self.d_layers = d_layers
		self.useAlpha = useAlpha
		self.useBeta = useBeta
		self.useGamma = useGamma
		self.useTau = useTau
		self.feature_map_shrink = feature_map_shrink
		self.feature_map_growth = feature_map_growth
		self.spatial_map_shrink = spatial_map_shrink
		self.spatial_map_growth = spatial_map_growth
		self.stage = stage
		self.loss = loss
		self.z_distr = z_distr
		self.activation = activation
		self.weight_init = weight_init
		self.learning_rate = lr
		self.beta1 = beta1
		self.beta2 = beta2
		self.epsilon = epsilon
		self.batch_size = batch_size
		self.sample_num = sample_num
		self.input_size = 128
		self.output_size = output_size
		self.g_batchnorm = g_batchnorm
		self.d_batchnorm = d_batchnorm
		self.normalize_z = normalize_z
		self.crop = crop
		self.visualize = visualize
		self.model_dir = model_dir
		self.model_dir_full = model_dir +  '/stage_'+self.stage+'_z'+str(self.z_dim)
		self.minibatch_std = minibatch_std
		self.use_wscale = use_wscale
		self.use_pixnorm = use_pixnorm
		self.D_loss_extra = D_loss_extra
		self.G_run_avg = G_run_avg
		self.oldSpecs = oldSpecs

		self.data = glob(os.path.join("../../celebA_dataset", 'celebA', '*.jpg'))
		self.data.sort()
		seed = 547
		np.random.seed(seed)
		np.random.shuffle(self.data)

		self.build_model()


	def build_model(self):
		if self.crop:
			image_dims = [self.output_size, self.output_size, 3] 
		else:
			image_dims = [self.input_size, self.input_size, 3]

		self.inputs = tf.placeholder(
            tf.float32, [self.batch_size] + image_dims, name='real_images')

		self.z = tf.placeholder(tf.float32, [None, self.z_dim], name='z')
		self.alpha = tf.placeholder(tf.float32, shape=(), name = 'alpha')
		self.beta = tf.placeholder(tf.float32, shape=(), name = 'beta')
		self.gamma = tf.placeholder(tf.float32, shape=(), name = 'gamma')
		self.tau = tf.placeholder(tf.float32, shape=(), name = 'tau')

		self.G = G(self.z, batch_size= self.batch_size, reuse = False, bn = self.g_batchnorm, layers = self.g_layers, activation = self.activation, output_dim = self.output_size,
			feature_map_shrink = self.feature_map_shrink, spatial_map_growth = self.spatial_map_growth, beta = self.beta, useBeta = self.useBeta,
			 use_wscale = self.use_wscale, use_pixnorm = self.use_pixnorm)
		self.D_real, self.D_real_logits = D(self.inputs, batch_size = self.batch_size, reuse = False, bn = self.d_batchnorm, layers = self.d_layers, activation = self.activation,
		 input_dim = self.input_size, feature_map_growth = self.feature_map_growth, spatial_map_shrink = self.spatial_map_shrink,
		  beta = self.beta, useBeta = self.useBeta, z_dim = self.z_dim, minibatch_std = self.minibatch_std, use_wscale = self.use_wscale)
		self.D_fake, self.D_fake_logits = D(self.G, batch_size = self.batch_size, reuse = True, bn = self.d_batchnorm, layers = self.d_layers, activation = self.activation,
		 input_dim = self.input_size, feature_map_growth = self.feature_map_growth, spatial_map_shrink = self.spatial_map_shrink,
		  beta = self.beta, useBeta = self.useBeta, z_dim = self.z_dim, minibatch_std = self.minibatch_std, use_wscale = self.use_wscale)


		"""loss function"""
		if self.loss == 'RaLS':
			# d_loss
			self.d_loss_real = tf.reduce_mean(
			    tf.square(self.D_real_logits - tf.reduce_mean(self.D_fake_logits) - 1))
			self.d_loss_fake = tf.reduce_mean(
			    tf.square(self.D_fake_logits - tf.reduce_mean(self.D_real_logits) + 1))
			self.d_loss = (self.d_loss_real + self.d_loss_fake) / 2
			if self.D_loss_extra:
				self.d_loss = self.d_loss + 0.001*tf.reduce_mean(tf.square(self.D_real_logits))

			# g_loss
			self.g_loss = (tf.reduce_mean(tf.square(self.D_fake_logits - tf.reduce_mean(self.D_real_logits))) / 2 
				+ tf.reduce_mean(tf.square(self.D_real_logits - tf.reduce_mean(self.D_fake_logits))) / 2)
		elif self.loss == 'ns':
			self.d_loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=self.D_real_logits,labels=tf.ones_like(self.D_real_logits)))
			self.d_loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=self.D_fake_logits,labels=tf.zeros_like(self.D_fake_logits)))
			self.d_loss = self.d_loss_real + self.d_loss_fake
			if self.D_loss_extra:
				self.d_loss = self.d_loss + 0.001*tf.reduce_mean(tf.square(self.D_real_logits))
			self.g_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=self.D_fake_logits,labels=tf.ones_like(self.D_fake_logits)))
		elif self.loss == 'wa':
			hyperparameter = 10
			gamma = tf.random_uniform(shape=[self.batch_size,1,1,1],minval=0., maxval=1.)
			#beta = tf.ones([batch_size,1,1,1],dtype=tf.float32)
			xhat = tf.add( tf.multiply(gamma,self.inputs), tf.multiply((1-gamma),self.G))

			_, D_xhat = D(xhat, batch_size = self.batch_size, reuse = True, bn = self.d_batchnorm, layers = self.d_layers, activation = self.activation, input_dim = self.input_size,
			feature_map_growth = self.feature_map_growth, spatial_map_shrink = self.spatial_map_shrink,
			 beta = self.beta, useBeta = self.useBeta, z_dim = self.z_dim, minibatch_std = self.minibatch_std, use_wscale = self.use_wscale)

			gradients = tf.gradients(D_xhat, xhat)[0] # is different between arch 1 and 2. Strange. The inputs are of different size, but just an upsampled version of the lower resolution version. Maybe that's why.
			# Since we take the gradient wrt xhat which is 4 times larger, when we sum the squares of gradients for each pixel we should get a larger gradient penalty for the larger image.
			#print('xhatshape', xhat.shape)_sample
			#print('idx: ', idx)
			#print('gradientdim', gradients) #(256,1,?,2) same as xhat
			slopes = tf.sqrt(tf.reduce_sum(tf.square(gradients), reduction_indices=[1,2,3]))
			#print('slpopedim:', slopes.shape) # (256,1)
			#gradient_penalty = tf.reduce_mean(tf.clip_by_value(slopes - 1., 0., np.infty)**2)
			gradient_penalty = tf.reduce_mean((slopes-1.)**2)
			self.d_loss_fake = tf.reduce_mean(self.D_fake_logits)
			self.d_loss_real = -tf.reduce_mean(self.D_real_logits) + hyperparameter*gradient_penalty

			self.g_loss = -tf.reduce_mean(self.D_fake_logits) 

			self.d_loss = self.d_loss_real + self.d_loss_fake
			if self.D_loss_extra:
				self.d_loss = self.d_loss + 0.001*tf.reduce_mean(tf.square(self.D_real_logits))


		#sampler
		self.inputs_sample = tf.placeholder(
			tf.float32, [self.sample_num] + image_dims, name='real_images_sample')

		self.sampler = G(self.z, batch_size= self.sample_num, reuse = True, bn = self.g_batchnorm, layers = self.g_layers, activation = self.activation, output_dim = self.output_size,
			feature_map_shrink = self.feature_map_shrink, spatial_map_growth = self.spatial_map_growth, beta = self.beta, useBeta = self.useBeta,
			 use_wscale = self.use_wscale, use_pixnorm = self.use_pixnorm)
		self.D_real_sample, self.D_real_logits_sample = D(self.inputs_sample, batch_size = self.sample_num, reuse = True, bn = self.d_batchnorm, layers = self.d_layers, activation = self.activation,
		 input_dim = self.input_size, feature_map_growth = self.feature_map_growth, spatial_map_shrink = self.spatial_map_shrink,
		   beta = self.beta, useBeta = self.useBeta, z_dim = self.z_dim, minibatch_std = self.minibatch_std, use_wscale = self.use_wscale)
		self.D_fake_sample, self.D_fake_logits_sample = D(self.G, batch_size = self.sample_num, reuse = True, bn = self.d_batchnorm, layers = self.d_layers, activation = self.activation,
		 input_dim = self.input_size, feature_map_growth = self.feature_map_growth, spatial_map_shrink = self.spatial_map_shrink,
		   beta = self.beta, useBeta = self.useBeta, z_dim = self.z_dim, minibatch_std = self.minibatch_std, use_wscale = self.use_wscale)


		if self.loss == 'RaLS':
			# d_loss
			self.d_loss_real_sample = tf.reduce_mean(
				tf.square(self.D_real_logits_sample - tf.reduce_mean(self.D_fake_logits_sample) - 1))
			self.d_loss_fake_sample = tf.reduce_mean(
				tf.square(self.D_fake_logits_sample - tf.reduce_mean(self.D_real_logits_sample) + 1))
			self.d_loss_sample = (self.d_loss_real_sample + self.d_loss_fake_sample) / 2
			if self.D_loss_extra:
				self.d_loss_sample = self.d_loss_sample + 0.001*tf.reduce_mean(tf.square(self.D_real_logits_sample))

			# g_loss
			self.g_loss_sample = (tf.reduce_mean(tf.square(self.D_fake_logits_sample - tf.reduce_mean(self.D_real_logits_sample))) / 2 +
				tf.reduce_mean(tf.square(self.D_real_logits_sample - tf.reduce_mean(self.D_fake_logits_sample))) / 2)
		elif self.loss == 'ns':
			self.d_loss_sample = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=self.D_real_logits_sample,labels=tf.ones_like(self.D_real_logits_sample)) + tf.nn.sigmoid_cross_entropy_with_logits(logits=self.D_fake_logits_sample,labels=tf.zeros_like(self.D_fake_logits)))
			self.g_loss_sample = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=self.D_fake_logits_sample,labels=tf.ones_like(self.D_fake_logits_sample)))
			if self.D_loss_extra:
				self.d_loss_sample = self.d_loss_sample + 0.001*tf.reduce_mean(tf.square(self.D_real_logits_sample))
		elif self.loss == 'wa':
			hyperparameter = 10
			gamma = tf.random_uniform(shape=[self.sample_num,1,1,1],minval=0., maxval=1.)
			#beta = tf.ones([batch_size,1,1,1],dtype=tf.float32)
			xhat = tf.add( tf.multiply(gamma,self.inputs_sample), tf.multiply((1-gamma),self.sampler))

			_, D_xhat = D(xhat, batch_size = self.sample_num, reuse = True, layers = self.d_layers, activation = self.activation, input_dim = self.input_size,
				feature_map_growth = self.feature_map_growth, spatial_map_shrink = self.spatial_map_shrink, z_dim = self.z_dim,
				 minibatch_std = self.minibatch_std, use_wscale = self.use_wscale)


			gradients = tf.gradients(D_xhat, xhat)[0]
			#print('xhatshape', xhat.shape)
			#print('idx: ', idx)
			#print('gradientdim', gradients) #(256,1,?,2) same as xhat
			slopes = tf.sqrt(tf.reduce_sum(tf.square(gradients), reduction_indices=[1,2,3]))
			#print('slpopedim:', slopes.shape) # (256,1)
			#gradient_penalty = tf.reduce_mean(tf.clip_by_value(slopes - 1., 0., np.infty)**2)
			gradient_penalty = tf.reduce_mean((slopes-1.)**2)
			self.gradient_penalty = gradient_penalty
			self.d_loss_fake_sample = tf.reduce_mean(self.D_fake_logits_sample)
			self.d_loss_real_sample = -tf.reduce_mean(self.D_real_logits_sample)

			self.g_loss_sample = -tf.reduce_mean(self.D_fake_logits_sample) 
			self.d_loss_sample_wo_gp = self.d_loss_real_sample + self.d_loss_fake_sample

			self.d_loss_sample = self.d_loss_sample_wo_gp + hyperparameter*gradient_penalty
			if self.D_loss_extra:
				self.d_loss_sample = self.d_loss_sample + 0.001*tf.reduce_mean(tf.square(self.D_real_logits_sample))

		"""data visualization"""
		self.z_sum = histogram_summary("z", self.z)
		self.d_real_sum = histogram_summary("d_real", self.D_real)
		self.d_fake_sum = histogram_summary("d_fake", self.D_fake)
		#self.G_sum = image_summary("G", tf.reshape(self.G,[self.batch_size, 128, 128, 3])) #HACK
		self.G_sum = image_summary("G", self.G)
		self.g_loss_sum = scalar_summary("g_loss", self.g_loss)
		self.d_loss_sum = scalar_summary("d_loss", self.d_loss)
		self.d_loss_real_sum = scalar_summary("d_loss_real", self.d_loss_real)
		self.d_loss_fake_sum = scalar_summary("d_loss_fake", self.d_loss_fake)

		t_vars = tf.trainable_variables()

		self.d_vars = [var for var in t_vars if 'd_' in var.name]
		self.g_vars = [var for var in t_vars if 'g_' in var.name]
		self.saver = tf.train.Saver()

	def train(self):

		d_optim = tf.train.AdamOptimizer(
			self.learning_rate,
			beta1=self.beta1,beta2 = self.beta2, epsilon= self.epsilon).minimize(
			self.d_loss,
			var_list=self.d_vars)

		g_optim = tf.train.AdamOptimizer(
			self.learning_rate,
			beta1=self.beta1,beta2 = self.beta2, epsilon= self.epsilon).minimize(
			self.g_loss,
			var_list=self.g_vars)

		try:
			tf.global_variables_initializer().run(session=self.sess)
		except BaseException:
			tf.initialize_all_variables().run(session=self.sess)

		self.g_sum = merge_summary([self.z_sum, self.d_fake_sum,
			self.G_sum, self.d_loss_fake_sum, self.g_loss_sum])
		self.d_sum = merge_summary(
			[self.d_real_sum, self.d_loss_real_sum, self.d_loss_sum])


		if not os.path.exists('../logs/'+self.model_dir_full):
			os.makedirs('../logs/'+self.model_dir_full)
		self.writer = SummaryWriter('../logs/'+self.model_dir_full, self.sess.graph)

		if self.z_distr == 'u':
			sample_z = np.random.uniform(-1, 1, size=(self.sample_num, 256)).astype(np.float32)
			if self.normalize_z:
				sample_z /= np.sqrt(np.sum(np.square(sample_z)))
		elif self.z_distr == 'g':
			sample_z = np.random.normal(0,1,size=(self.sample_num, 256)).astype(np.float32)
			if self.normalize_z:
				sample_z /= np.sqrt(np.sum(np.square(sample_z)))

		sample_z = sample_z[:,0:self.z_dim]
		# sample_z = np.full((self.sample_num, self.z_dim), 0.1).astype(np.float32)

		alpha = np.float32(0.0)
		beta = np.float32(0.0)
		gamma = np.float32(self.z_dim/2)
		tau = np.float32(0.0)

		sample_files = self.data[0:self.sample_num]
		if self.useAlpha == 'n':
			sample = [
				get_image(
					sample_file,
					input_height=self.input_size,
					input_width=self.input_size,
					resize_height=self.output_size,
					resize_width=self.output_size,
					crop=self.crop) for sample_file in sample_files]
		elif self.useAlpha == 'y':
			sample = [
			get_image_interpolate(
				sample_file, z_dim = self.z_dim,
				input_height=self.input_size,
				input_width=self.input_size,
				resize_height=self.output_size,
				resize_width=self.output_size,
				crop=self.crop, alpha = 1.0) for sample_file in sample_files]

		sample_inputs = np.array(sample).astype(np.float32)

		counter = 0
		start_time = time.time()

		# Vectors for plotting
		gp_vec = np.array([])
		d_loss_vec = np.array([])
		d_loss_wo_gp_vec = np.array([])

		D_real_vec = np.array([])
		D_fake_vec = np.array([])

		d_loss_real_vec = np.array([])
		d_loss_fake_vec = np.array([])

		xaxis = np.array([])


		if not os.path.exists('../loss/'+self.model_dir_full):
			os.makedirs('../loss/'+self.model_dir_full)

		could_load, model_counter, message = self.load(weight_init = self.weight_init)
		if could_load:
			counter = model_counter
			print(" [*] " + message)
		else:
			print(" [!] " + message)

		for epoch in xrange(self.epochs):


			np.random.shuffle(self.data)
			batch_idxs = len(self.data) // self.batch_size

			for idx in xrange(0, batch_idxs):
				batch_files = self.data[idx * self.batch_size:(idx + 1) * self.batch_size] # replace 0 with idx
				if self.useAlpha == 'n':
					batch = [
						get_image(
							batch_file,
							input_height=self.input_size,
							input_width=self.input_size,
							resize_height=self.output_size,
							resize_width=self.output_size,
							crop=self.crop) for batch_file in batch_files]
				elif self.useAlpha == 'y':
					batch = [
						get_image_interpolate(
							batch_file, z_dim = self.z_dim,
							input_height=self.input_size,
							input_width=self.input_size,
							resize_height=self.output_size,
							resize_width=self.output_size,
							crop=self.crop, alpha = alpha) for batch_file in batch_files]
				batch_images = np.array(batch).astype(np.float32)

                #batch_images_shape = batch_images.shape #HACK
                #batch_images = np.reshape(batch_images, [batch_images_shape[0], batch_images_shape[3], batch_images_shape[1], batch_images_shape[2]]) #HACK

				if self.z_distr == 'u':
					batch_z = np.random.uniform(-1, 1, size=(self.batch_size, 256)).astype(np.float32)
					if self.normalize_z:
						batch_z /= np.sqrt(np.sum(np.square(batch_z)))
				elif self.z_distr == 'g':
					batch_z = np.random.normal(0,1,size=(self.batch_size, 256)).astype(np.float32)
					if self.normalize_z:
						batch_z /= np.sqrt(np.sum(np.square(batch_z)))

				batch_z = batch_z[:,0:self.z_dim]
				# batch_z = np.full((self.batch_size, self.z_dim), 0.1).astype(np.float32)

				if np.mod(counter, 100) == 0:
					d_loss, D_real, D_fake, gp, d_loss_fake, d_loss_real, d_loss_wo_gp = self.sess.run(
						[self.d_loss_sample, self.D_real_sample, self.D_fake_sample, self.gradient_penalty,
						 self.d_loss_fake_sample, self.d_loss_real_sample, self.d_loss_sample_wo_gp],
						feed_dict={
							self.z: sample_z,
							self.inputs_sample: sample_inputs, self.beta: beta
						},
					)
					D_real = np.mean(D_real)
					D_fake = np.mean(D_fake)

					gp_vec = np.append(gp_vec, gp)
					d_loss_vec = np.append(d_loss_vec, d_loss)
					d_loss_wo_gp_vec = np.append(d_loss_wo_gp_vec, d_loss_wo_gp)

					D_real_vec = np.append(D_real_vec, D_real)
					D_fake_vec = np.append(D_fake_vec, D_fake)

					d_loss_real_vec = np.append(d_loss_real_vec, d_loss_real)
					d_loss_fake_vec = np.append(d_loss_fake_vec, d_loss_fake)

					xaxis = np.append(xaxis, counter*self.batch_size)

					if np.mod(counter, 10000) == 0:	
						plt.figure()
						plt.grid(True)
						plt.xlabel('Real Examples Shown')
						plt.ylabel('Loss')
						plt.title('Discriminator Loss')
						plt.tight_layout()
						plt.plot(xaxis, gp_vec,label = 'gp')
						plt.plot(xaxis, d_loss_vec,label = 'total')
						plt.plot(xaxis, d_loss_wo_gp_vec, label = '-real+fake')
						plt.legend()

						plt.savefig('../loss/' + self.model_dir_full + '/d_loss_' + str(counter*self.batch_size) +'.png')
						plt.close()

						plt.figure()
						plt.grid(True)
						plt.xlabel('Real Examples Shown')
						plt.ylabel('Loss')
						plt.title('Discriminator Probabilities on Real and Fake Data')
						plt.tight_layout()
						plt.plot(xaxis, D_real_vec,label = 'real')
						plt.plot(xaxis, D_fake_vec,label = 'fake')
						plt.legend()

						plt.savefig('../loss/' + self.model_dir_full + '/d_prob_' + str(counter*self.batch_size) +'.png')
						plt.close()

						plt.figure()
						plt.grid(True)
						plt.xlabel('Real Examples Shown')
						plt.ylabel('Loss')
						plt.title('Discriminator Loss Values on Real and Fake Data')
						plt.tight_layout()
						plt.plot(xaxis, d_loss_real_vec,label = '-real')
						plt.plot(xaxis, d_loss_fake_vec,label = 'fake')
						plt.legend()

						plt.savefig('../loss/' + self.model_dir_full + '/d_loss_val_' + str(counter*self.batch_size) +'.png')
						plt.close()


				# # Run g_optim twice to make sure that d_loss does not go to
				# # zero (different from paper)
				# _, summary_str = self.sess.run([g_optim, self.g_sum], feed_dict={
				# 	self.inputs: batch_images, self.z: batch_z})

				# self.writer.add_summary(summary_str, counter)
				# if np.mod(counter, 1) == 0 or np.mod(counter, 1) == 1:
				# 	errD_fake = self.d_loss_fake.eval(
				# 		{self.inputs: batch_images, self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	errD_real = self.d_loss_real.eval(
				# 		{self.inputs: batch_images, self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	errG = self.g_loss.eval(
				# 		{self.inputs: batch_images, self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	d_real_logits = self.D_real_logits.eval({self.inputs: batch_images, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	d_fake_logits = self.D_fake_logits.eval({self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# g_out = self.G.eval({self.inputs: batch_images, self.z: batch_z, self.beta: beta})
				# 	print(
				# 		"Epoch: [%2d] [%4d/%4d] time: %4.4f, d_loss: %.8f, g_loss: %.8f" %
				# 			(epoch, idx, batch_idxs, time.time() - start_time, errD_real, errG)) # errD_fake + errD_real
				# # print('image: ', batch_images)
				# print('d_fake_logits: ', d_fake_logits)
				# print('d_real_logits: ', d_real_logits)
				# print('errD_fake: ', errD_fake)
				# print('g_out: ', g_out)# errD_fake + errD_real
				

				# # Update D network
				# _, summary_str = self.sess.run([d_optim, self.d_sum], feed_dict={
				# 	self.inputs: batch_images, self.z: batch_z, self.alpha: alpha, self.beta: beta})

				# self.writer.add_summary(summary_str, counter)

				# # Update G network
				# _, summary_str = self.sess.run([g_optim, self.g_sum], feed_dict={
				# 	self.z: batch_z, self.alpha: alpha, self.beta: beta})

				# self.writer.add_summary(summary_str, counter)

				if np.mod(counter, 1000) == 0:
					samples, d_loss, g_loss, D_real, D_fake = self.sess.run(
						[self.sampler, self.d_loss_sample, self.g_loss_sample, self.D_real_sample, self.D_fake_sample],
						feed_dict={
							self.z: sample_z,
							self.inputs_sample: sample_inputs, self.beta: beta
						},
					)
					if not os.path.exists('../{}/{}'.format('train_samples', self.model_dir_full)):
						os.makedirs('../{}/{}'.format('train_samples', self.model_dir_full))

					save_images(
						samples, 
							[int(np.sqrt(self.sample_num)),int(np.sqrt(self.sample_num))], '../{}/{}/train_{:02d}_{:04d}.png'.format(
							'train_samples', self.model_dir_full, epoch, idx))
					# print("[Sample] d_loss: %.8f, g_loss: %.8f" %
					# 	(d_loss, g_loss))
				# if np.mod(counter, 5) == 0:
					# self.save(counter)

				# Update D network
				_, summary_str = self.sess.run([d_optim, self.d_sum], feed_dict={
					self.inputs: batch_images, self.z: batch_z, self.beta: beta})

				self.writer.add_summary(summary_str, counter)

				# Update G network
				_, summary_str = self.sess.run([g_optim, self.g_sum], feed_dict={
					self.z: batch_z, self.beta: beta})

				self.writer.add_summary(summary_str, counter)

				if alpha < 1:
					alpha = alpha + 0.25/batch_idxs#0.5
				if beta < 1:
					beta = beta + 0.25/batch_idxs#0.5 # might have to experiment with this ratio
				if gamma < self.z_dim:
					gamma = gamma + (self.z_dim/2)*0.25/batch_idxs #0.25*self.z_dim # might have to experiment with this ratio
				if tau < 0.5:
					tau = tau + 0.125/batch_idxs #0.25

				if np.mod(counter, 5000) == 0:
					self.save(counter)
				counter += 1
				# beta = 1.0
				# g_out = self.sess.run(self.G, feed_dict={self.z: batch_z, self.beta: beta})
				# print('g_out: ', g_out)
				# break
				# if idx == 2:  # REMOVE LATER!!!
				# 	alpha = 1.0
				# 	beta = 1.0
				# 	gamma = self.z_dim
				# 	tau = 0.5
				# 	errD_fake = self.d_loss_fake.eval(
				# 		{self.inputs: batch_images, self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	errD_real = self.d_loss_real.eval(
				# 		{self.inputs: batch_images, self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	errG = self.g_loss.eval(
				# 		{self.inputs: batch_images, self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	d_real_logits = self.D_real_logits.eval({self.inputs: batch_images, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	d_fake_logits = self.sess.run(self.D_fake_logits, feed_dict={self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
				# 	g_out = self.sess.run(self.G, feed_dict={self.z: batch_z, self.beta: beta, self.gamma: gamma, self.tau: tau})
	                
				# 	print(
				# 		"Epoch: [%2d] [%4d/%4d] time: %4.4f, d_loss: %.8f, g_loss: %.8f" %
				# 			(epoch, idx, batch_idxs, time.time() - start_time, errD_real, errG)) # errD_fake + errD_real
				# 	print('d_fake_logits: ', d_fake_logits)
				# 	print('d_real_logits: ', d_real_logits)
				# 	print('errD_fake: ', errD_fake)
				# 	print('g_out: ', g_out)
				# 	samples, d_loss, g_loss, D_real, D_fake = self.sess.run(
				# 		[self.sampler, self.d_loss_sample, self.g_loss_sample, self.D_real_sample, self.D_fake_sample],
				# 		feed_dict={
				# 			self.z: sample_z,
				# 			self.inputs_sample: sample_inputs, self.beta: beta, self.gamma: gamma, self.tau: tau
				# 		},
				# 	)
				# 	print("[Sample] d_loss: %.8f, g_loss: %.8f" %
				# 		(d_loss, g_loss))
				# 	self.save(counter)
				# 	break

    # @property
    # def model_dir(self):
    #     return "Arch{}_Zd{}_L{}_Bs{}_Lr{}_Zd{}_Iwh{}_Owh{}_Bn{}_classic_hopefix".format(
    #         self.architecture, self.z_dim, self.loss, self.batch_size, self.learning_rate, self.zdistribution,
    #         self.input_height, self.output_width, str(self.batchnorm))

	def save(self, step):
		model_name = "model"

		if not os.path.exists('../models/'+self.model_dir_full):
			os.makedirs('../models/'+self.model_dir_full)

		self.saver.save(self.sess, '../models/' + self.model_dir_full + '/' + model_name, global_step=step)

	# def load(self):
	# 	import re
	# 	print(" [*] Reading models...")

	# 	ckpt = tf.train.get_checkpoint_state('../models/'+self.model_dir)
	# 	if ckpt and ckpt.model_checkpoint_path:
	# 		ckpt_name = os.path.basename(ckpt.model_checkpoint_path)
	# 		self.saver.restore(self.sess, os.path.join('../models',
	# 			self.model_dir, ckpt_name))
	# 		counter = int(
	# 			next(re.finditer("(\d+)(?!.*\d)", ckpt_name)).group(0))
	# 		print(" [*] Success to read {}".format(ckpt_name))
	# 		return True, counter
	# 	else:
	# 		print(" [*] Failed to find the model")
	# 		return False, 0

	def load(self, weight_init = 'z'):
		import re
		print(" [*] Reading models...")
		try:
			zList = os.listdir('../models/'+self.model_dir)
		except:
			variables = tf.trainable_variables()
			for v in variables:
				tensor_name = v.name.split(':')[0]
				# print('tensor name: ', tensor_name)
			return False, 0, 'First Training Cycle'
	
		old_model_location = '../models/'+self.model_dir+'/stage_'+self.oldSpecs["stage"]+'_z'+str(self.oldSpecs['z_dim'])
		ckpt = tf.train.get_checkpoint_state(old_model_location)

		ckpt_name = os.path.basename(ckpt.model_checkpoint_path)
		old_model_location = old_model_location + '/' + ckpt_name

		if self.stage == 'i':
			# restore the old layers and add two new layers in generator and discriminator
			reader = tf.train.NewCheckpointReader(old_model_location)
			# I CAN USE THIS METHOD WHEN I KNOW WHAT LAYERS CONTAIN THE SAME WEIGHTS, BUT FIRST I NEED TO FIND THAT SOMEHOW
			restore_dict = dict()
			variables = tf.trainable_variables()
			discVar = tf.trainable_variables(scope = 'discriminator')
			for v in variables:
				tensor_name = v.name.split(':')[0]
				# print('tensor name: ', tensor_name)
				if reader.has_tensor(tensor_name) and 'generator' in tensor_name:
					restore_dict[tensor_name] = v
					# print('exists in old generator')
				elif reader.has_tensor(tensor_name) and ('out' in tensor_name or 'h1/' in tensor_name):
					restore_dict[tensor_name] = v
					# print('exists in old discriminator chill')
				elif reader.has_tensor(tensor_name):
					name_in_graph = tensor_name.split('/')
					#print(name_in_graph)
					name = name_in_graph[1]
					#print(name)
					if name[-2].isdigit():
						nbr = int(name[-2:])+2
						name = name[:-2]+str(nbr)
					else:
						nbr = int(name[-1])+2
						name = name[:-1]+str(nbr)
					name_in_graph[1] = name
					# print(name)
					s = '/'
					name_in_graph = s.join(name_in_graph)
					# print(name_in_graph)
					for var in discVar:
						varname = var.name.split(':')[0]
						# print(varname)
						if varname == name_in_graph:
							var_restore = var
							break
					restore_dict[tensor_name] = var_restore
					# print('exists in old discriminator')

			# print('done')
			saver = tf.train.Saver(restore_dict)
			saver.restore(self.sess, old_model_location)

			return True, 0, 'Added two more layers and restored the old layers, doubling the output dimension'
		elif self.stage == 'f':
			# same number of layers as before, but now we extend the number of channels for the layers
			# we are already in a session. We can easily create a dictionary and restore in the generator layer h4 and the final conv1x1. They have the same names as in the previous network.
			# In the discriminator I can restore h1, h2, h3 easily. We have also already initialized all weights previously, which is nice. The next problem is how we restore the partially new layers
			# In order to do that we need to extract the useful feature maps from the previous network checkpoint and use the assign function for the new network. 

			# Restore the not grown layers in discriminator and generator
			reader = tf.train.NewCheckpointReader(old_model_location)
			restore_dict = dict()
			partial_restore_dict = dict()
			for v in tf.trainable_variables():
				tensor_name = v.name.split(':')[0]
				# print('tensor name: ', tensor_name)
				name = tensor_name.split('/')
				name = name[1]
				if name[-2].isdigit():
					nbr = int(name[-2:])
				elif name[-1].isdigit():
					nbr = int(name[-1])

				if reader.has_tensor(tensor_name) and 'generator/g_h1/kernel' not in tensor_name:
					restore_dict[tensor_name] = v
					# print('JAtensor name: ', tensor_name)
				else:
					partial_restore_dict[tensor_name] = reader.get_tensor(tensor_name)
			saver = tf.train.Saver(restore_dict)
			saver.restore(self.sess, old_model_location)

			for tensor_name, tensorValue in partial_restore_dict.items():
				# # retrieve tensor from current graph
				print('tensorname: ', tensor_name)
				tensor = tf.get_default_graph().get_tensor_by_name(tensor_name+':0')
				print('oldtensorshape: ', tensorValue.shape)
				print('newtensorshape: ', tensor.shape)
				tensor_name_split = tensor_name.split('/')
				stddev = np.sqrt(2/self.z_dim)
				filterSize = tensorValue.shape[1]
				maps = tensorValue.shape[0]
				channels = maps
				imSize = tensorValue.shape[1]/256
				w = int(np.sqrt(imSize))
				h = w
				tensorValue = np.reshape(tensorValue, [channels, 4, 4, 256])
				stddev = np.sqrt(2/(self.z_dim))
				if self.use_wscale:
					factor = np.sqrt(2)
					temp = np.concatenate((factor*tensorValue, np.random.normal(0,1,(tensorValue.shape[0],tensorValue.shape[1],tensorValue.shape[2],tensorValue.shape[3]))), axis = 0)
					# temp = np.concatenate((temp,np.random.normal(0,stddev,(temp.shape[0],temp.shape[1],temp.shape[2],temp.shape[3]))),axis = 0)
					temp = np.reshape(temp, [maps*2,filterSize])
					temp = temp.astype(np.float32)
				else:
					temp = np.concatenate((tensorValue, np.random.normal(0,stddev,(tensorValue.shape[0],tensorValue.shape[1],tensorValue.shape[2],tensorValue.shape[3]))), axis = 0)
					# temp = np.concatenate((temp,np.random.normal(0,stddev,(temp.shape[0],temp.shape[1],temp.shape[2],temp.shape[3]))),axis = 0)
					temp = np.reshape(temp, [maps*2,filterSize])
					temp = temp.astype(np.float32)
				assign_op = tf.assign(tensor, temp)
				self.sess.run(assign_op)


			return True, 0, 'Added feature channels and initialized the new channels with '+weight_init+', doubled the latent space dimension'
