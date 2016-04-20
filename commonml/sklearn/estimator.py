# coding: utf-8

from logging import getLogger

import six

from chainer import Link, Chain, ChainList
from chainer import cuda, Function, gradient_check, Variable, optimizers, serializers, utils
import chainer

import chainer.functions as F
import chainer.links as L
import numpy as np
from sklearn.base import BaseEstimator
from scipy.sparse.base import spmatrix

logger = getLogger('commonml.sklearn.estimator')


class ChainerEstimator(BaseEstimator):

    def __init__(self, model, optimizer=optimizers.SGD(), batch_size=100, n_epoch=20, report=10, gpu=-1, **params):
        self.model = model
        if gpu >= 0:
            cuda.get_device(0).use()
            self.model.to_gpu()
        self.optimizer = optimizer
        self.optimizer.setup(self.model)
        self.n_epoch = n_epoch
        self.report = report
        self.batch_size = batch_size
        self.gpu = gpu

    def fit(self, X, y=None):
        if y is None:
            raise ValueError('y is None.')

        xp = np if self.gpu < 0 else cuda.cupy

        is_spmatrix = isinstance(X, spmatrix)
        data_size = X.shape[0] if is_spmatrix else len(X)

        for epoch in six.moves.range(self.n_epoch):
            logger.info(u'epoch {epoch}'.format(epoch=epoch))
            indexes = np.random.permutation(data_size)
            for i in six.moves.range(0, data_size, self.batch_size):
                # logger.info(u'Processing data[{0}:{1}]'.format(i, i + self.batch_size))
                x1 = X[indexes[i: i + self.batch_size]]
                y1 = y[indexes[i: i + self.batch_size]]
                if is_spmatrix:
                    x1 = x1.toarray()
                if isinstance(y1, spmatrix):
                    y1 = y1.toarray()
                x2 = Variable(xp.asarray(x1))
                y2 = Variable(xp.asarray(y1))
                self.optimizer.update(self.model, x2, y2)

            if self.report > 0 and epoch % self.report == 0:
                sum_loss, sum_accuracy = 0, 0
                for i in six.moves.range(0, data_size, self.batch_size):
                    x1 = X[indexes[i: i + self.batch_size]]
                    y1 = y[indexes[i: i + self.batch_size]]
                    if is_spmatrix:
                        x1 = x1.toarray()
                    if isinstance(y1, spmatrix):
                        y1 = y1.toarray()
                    x2 = Variable(xp.asarray(x1))
                    y2 = Variable(xp.asarray(y1))
                    loss = self.model(x2, y2, train=False)
                    sum_loss += loss.data * len(x1)
                mean_loss = sum_loss / data_size
                logger.info(' -> loss {0}'.format(mean_loss))

    def predict(self, X):
        xp = np if self.gpu < 0 else cuda.cupy

        is_spmatrix = isinstance(X, spmatrix)
        data_size = X.shape[0] if is_spmatrix else len(X)

        results = None
        for i in six.moves.range(0, data_size, self.batch_size):
            end = i + self.batch_size
            x1 = X[i: end if end < data_size else data_size]
            if is_spmatrix:
                x1 = x1.toarray()
            x2 = Variable(xp.asarray(x1))
            pred = self.model.predictor(x2, train=False)
            if results is None:
                results = cuda.to_cpu(pred.data)
            else:
                results = np.concatenate((results, cuda.to_cpu(pred.data)), axis=0)

        return results