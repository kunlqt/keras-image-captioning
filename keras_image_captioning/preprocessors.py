import numpy as np

from keras.applications import inception_v3
from keras.preprocessing import sequence as keras_seq
from keras.preprocessing.image import img_to_array, load_img
from keras.preprocessing.text import Tokenizer

from .config import active_config


class ImagePreprocessor(object):
    IMAGE_SIZE = (299, 299)

    def __init__(self, image_data_generator=None):
        self._image_data_generator = image_data_generator
        self._do_random_transform = image_data_generator is not None

    def preprocess_images(self, img_paths):
        return map(self._preprocess_an_image, img_paths)

    def preprocess_batch(self, img_list):
        return np.array(img_list)

    def _preprocess_an_image(self, img_path):
        img = load_img(img_path, target_size=self.IMAGE_SIZE)
        img_array = img_to_array(img)
        img_array = inception_v3.preprocess_input(img_array)
        if self._do_random_transform:
            img_array = self._image_data_generator.random_transform(img_array)

        return img_array


class CaptionPreprocessor(object):
    EOS_TOKEN = 'eos'

    def __init__(self, rare_words_handling=None, words_min_occur=None):
        """
        If an arg is None, it will get its value from config.active_config.
        Args:
          rare_words_handling: {'nothing'|'discard'|'change'}
          words_min_occur: words whose occurrences are less than this are
                           considered rare words
        """
        self._tokenizer = Tokenizer()
        self._rare_words_handling = (rare_words_handling or
                                     active_config().rare_words_handling)
        self._words_min_occur = (words_min_occur or
                                 active_config().words_min_occur)

    @property
    def vocab_size(self):
        return len(self._tokenizer.word_index)

    def fit_on_captions(self, captions_txt):
        captions_txt = self._add_eos(captions_txt)
        # TODO Handle rare words
        self._tokenizer.fit_on_texts(captions_txt)

    def encode_captions(self, captions_txt):
        captions_txt = self._add_eos(captions_txt)
        return self._tokenizer.texts_to_sequences(captions_txt)

    def decode_captions(self, captions_encoded):
        # TODO
        raise NotImplementedError

    def preprocess_batch(self, captions_label_encoded):
        captions = keras_seq.pad_sequences(captions_label_encoded,
                                           padding='post')
        # Because the number of timesteps/words resulted by the model is
        # maxlen(captions) + 1 (because the first "word" is the image).
        captions_extended1 = keras_seq.pad_sequences(captions,
                                                maxlen=captions.shape[-1] + 1,
                                                padding='post')
        captions_one_hot = map(self._tokenizer.sequences_to_matrix,
                               np.expand_dims(captions_extended1, -1))
        captions_one_hot = np.array(captions_one_hot, dtype='int')

        # Decrease/shift word index by 1.
        # Shifting `captions_one_hot` makes the padding word
        # (index=0, encoded=[1, 0, ...]) encoded all zeros ([0, 0, ...]),
        # so its cross entropy loss will be zero.
        captions_decreased = captions.copy()
        captions_decreased[captions_decreased > 0] -= 1
        captions_one_hot_shifted = captions_one_hot[:, :, 1:]

        captions_input = captions_decreased
        captions_output = captions_one_hot_shifted
        return captions_input, captions_output

    def _add_eos(self, captions):
        return map(lambda x: x + ' ' + self.EOS_TOKEN, captions)