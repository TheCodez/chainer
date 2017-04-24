import numpy

from chainer import cuda
from chainer.functions.connection import deconvolution_2d
from chainer import initializers
from chainer import link


class Deconvolution2D(link.Link):

    """Two dimensional deconvolution function.

    This link wraps the :func:`~chainer.functions.deconvolution_2d` function
    and holds the filter weight and bias vector as parameters.

    Args:
        in_channels (int): Number of channels of input arrays. If it is
            ``None`` or omitted, parameter initialization will be deferred
            until the first forward data pass at which time the size will be
            determined.
        out_channels (int): Number of channels of output arrays.
        ksize (int or pair of ints): Size of filters (a.k.a. kernels).
            ``ksize=k`` and ``ksize=(k, k)`` are equivalent.
        stride (int or pair of ints): Stride of filter applications.
            ``stride=s`` and ``stride=(s, s)`` are equivalent.
        pad (int or pair of ints): Spatial padding width for input arrays.
            ``pad=p`` and ``pad=(p, p)`` are equivalent.
        nobias (bool): If ``True``, then this function does not use the bias
            term.
        outsize (tuple): Expected output size of deconvolutional operation.
            It should be pair of height and width :math:`(out_H, out_W)`.
            Default value is ``None`` and the outsize is estimated by
            input size, stride and pad.
        initialW (callable): Weight initializer.
            It should be a callable that takes ``numpy.ndarray`` or
            ``cupy.ndarray`` and edits its value.
            If it is ``None``, the default initializer is used.
            If it is `numpy.ndarray`, the array is used as initial
            weight value.
        initial_bias (callable): Bias initializer.
            It should be a callable that takes ``numpy.ndarray`` or
            ``cupy.ndarray`` and edits its value.
            If ``None``, the default initializer is used.
            If it is `numpy.ndarray`, the array is used as initial bias value.
        deterministic (bool): The output of this link can be
            non-deterministic when it uses cuDNN.
            If this option is ``True``, then it forces cuDNN to use
            a deterministic algorithm. This option is only available for
            cuDNN version >= v4.

    The filter weight has four dimensions :math:`(c_I, c_O, k_H, k_W)`
    which indicate the number of input channels, output channels,
    height and width of the kernels, respectively.
    The filter weight is initialized with i.i.d. Gaussian random samples, each
    of which has zero mean and deviation :math:`\\sqrt{1/(c_I k_H k_W)}` by
    default.

    The bias vector is of size :math:`c_O`.
    Its elements are initialized by ``bias`` argument.
    If ``nobias`` argument is set to True, then this function does not hold
    the bias parameter.

    .. seealso::
       See :func:`chainer.functions.deconvolution_2d` for the definition of
       two-dimensional convolution.

    .. seealso::
        See :func:`chainer.links.Convolution2D` for the examples of ways to
        give arguments to this link.

    .. admonition:: Example

        There are several ways to make a Deconvolution2D link.

        Let an input vector ``x`` be:

        >>> x = np.arange(1 * 3 * 10 * 10, dtype='f').reshape(1, 3, 10, 10)

        1. Give the first three arguments explicitly:

            In this case, all the other arguments are set to the default
            values.

            >>> l = L.Deconvolution2D(3, 7, 4)
            >>> y = l(x)
            >>> y.shape
            (1, 7, 13, 13)

        2. Omit ``in_channels`` or fill it with ``None``:

            The below two cases are the same.

            >>> l = L.Deconvolution2D(7, 4)
            >>> y = l(x)
            >>> y.shape
            (1, 7, 13, 13)

            >>> l = L.Deconvolution2D(None, 7, 4)
            >>> y = l(x)
            >>> y.shape
            (1, 7, 13, 13)

            When you omit the first argument, you need to specify the other
            subsequent arguments from ``stride`` as keyword arguments. So the
            below two cases are the same.

            >>> l = L.Deconvolution2D(None, 7, 4, 2, 1)
            >>> y = l(x)
            >>> y.shape
            (1, 7, 20, 20)

            >>> l = L.Deconvolution2D(7, 4, stride=2, pad=1)
            >>> y = l(x)
            >>> y.shape
            (1, 7, 20, 20)

    """

    def __init__(self, in_channels, out_channels, ksize=None, stride=1, pad=0,
                 nobias=False, outsize=None, initialW=None, initial_bias=None,
                 deterministic=False):
        super(Deconvolution2D, self).__init__()

        if ksize is None:
            out_channels, ksize, in_channels = in_channels, out_channels, None

        self.ksize = ksize
        self.stride = _pair(stride)
        self.pad = _pair(pad)
        self.outsize = (None, None) if outsize is None else outsize
        if initialW is None:
            self.initialW = initializers.HeNormal(1.0 / numpy.sqrt(2))
        else:
            self.initialW = initialW
        self.out_channels = out_channels
        self.deterministic = deterministic

        self.add_param('W', initializer=initializers._get_initializer(
            initialW))
        if in_channels is not None:
            self._initialize_params(in_channels)

        if nobias:
            self.b = None
        else:
            if isinstance(initial_bias, (numpy.ndarray, cuda.ndarray)):
                assert initial_bias.shape == (out_channels,)
            if initial_bias is None:
                initial_bias = initializers.Constant(0)
            bias_initializer = initializers._get_initializer(initial_bias)
            self.add_param('b', out_channels, initializer=bias_initializer)

    def _initialize_params(self, in_channels):
        kh, kw = _pair(self.ksize)
        W_shape = (in_channels, self.out_channels, kh, kw)
        self.W.initialize(W_shape)

    def __call__(self, x):
        if self.W.data is None:
            self._initialize_params(x.shape[1])
        return deconvolution_2d.deconvolution_2d(
            x, self.W, self.b, self.stride, self.pad,
            self.outsize, deterministic=self.deterministic)


def _pair(x):
    if hasattr(x, '__getitem__'):
        return x
    return x, x
