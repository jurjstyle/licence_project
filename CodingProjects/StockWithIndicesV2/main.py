from __future__ import absolute_import, division, print_function, unicode_literals
from typing import List

import tensorflow as tf

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
from absl import app, flags, logging
from absl.flags import FLAGS
import math


flags.DEFINE_string('company_ticker_symbol', 'mro', 'shortcut name of the company')
flags.DEFINE_string('stocks_path', '../Data/Kaggle_Stocks/Stocks', 'path for the stock information about the company')
flags.DEFINE_string('company_file_ending', '.us.txt', 'ending name for the file containing stock information')

flags.DEFINE_list('removed_columns_stock_company', 'OpenInt', 'list of columns to remove for stock company dataframe')

flags.DEFINE_boolean('use_stock_indices', True, 'whether to use or not stock indices for the network')
flags.DEFINE_list('stock_indices_list', 'S&P500, DowJonesIndustrial, NasdaqComposite', 'names of stock indices used')

flags.DEFINE_integer('percentage_split', 80, 'Percentage of training vs validation data')
flags.DEFINE_string('output_directory', 'output', 'Output directory for the plots')
flags.DEFINE_string('checkpoints_directory', 'checkpoints', 'Output directory for the checkpoints weights')

flags.DEFINE_integer('past_history_no_days', 30, 'The no days to use for past history data')
flags.DEFINE_integer('future_prediction_no_days', 3, 'The no days to use for predicting in the future')

flags.DEFINE_integer('batch_size', 128, 'batch size for training')
flags.DEFINE_integer('no_epochs', 30, 'no epochs for training')


def read_company_stock_data(company_ticker_symbol: str) -> pd.DataFrame:
    stocks_company_filepath = os.path.join(FLAGS.stocks_path, company_ticker_symbol + FLAGS.company_file_ending)
    stock_dataframe: pd.DataFrame = pd.read_csv(stocks_company_filepath)
    return stock_dataframe


def remove_unnecessary_company_stock_columns(stock_dataframe: pd.DataFrame) -> pd.DataFrame:
    logging.info("Columns to be removed from company stock data: " + str(FLAGS.removed_columns_stock_company))

    stock_dataframe.drop(columns=FLAGS.removed_columns_stock_company, inplace=True)
    return stock_dataframe


def rename_company_stock_columns(stock_dataframe: pd.DataFrame, company_ticker_symbol: str) -> pd.DataFrame:
    stock_dataframe.rename(columns=lambda name: company_ticker_symbol + "_" + name, inplace=True)
    return stock_dataframe


def drop_very_old_data(stock_dataframe: pd.DataFrame) -> pd.DataFrame:
    stock_dataframe = stock_dataframe[pd.to_datetime(stock_dataframe['Date']).dt.year >= 1990]
    return stock_dataframe


def prepare_company_stock_data(company_ticker_symbol: str) -> pd.DataFrame:
    stock_dataframe: pd.DataFrame = read_company_stock_data(company_ticker_symbol)
    stock_dataframe = remove_unnecessary_company_stock_columns(stock_dataframe)
    stock_dataframe = drop_very_old_data(stock_dataframe)
    stock_dataframe = rename_company_stock_columns(stock_dataframe, company_ticker_symbol)

    print(stock_dataframe.head())
    print(stock_dataframe.tail())
    return stock_dataframe


def read_singular_stock_index(filename: str) -> pd.DataFrame:
    parent_path = ".."
    stock_index_path = os.path.join(parent_path, filename)
    stock_index_dataframe: pd.DataFrame = pd.read_csv(stock_index_path)
    return stock_index_dataframe


def rename_stock_index_columns(stock_dataframe: pd.DataFrame, stock_index_name: str) -> pd.DataFrame:
    stock_dataframe.rename(columns=lambda column_name: stock_index_name + "_" + column_name, inplace=True)
    return stock_dataframe


def preprocess_stock_indexes() -> pd.DataFrame:
    stocks_indexes_dataframes_columns = FLAGS.stock_indices_list
    filenames_list = [name + '.csv' for name in stocks_indexes_dataframes_columns]
    stocks_indexes_dataframes = []

    for filename in filenames_list:
        stock_index_dataframe = read_singular_stock_index(filename)
        stock_index_dataframe = drop_very_old_data(stock_index_dataframe)
        # here for the filename used for renaming - get string partition before substring
        stock_index_dataframe = rename_stock_index_columns(stock_index_dataframe, filename.partition('.csv')[0])

        print(stock_index_dataframe.head())
        print(stock_index_dataframe.tail())
        stocks_indexes_dataframes.append(stock_index_dataframe)

    reunited_dataframe = stocks_indexes_dataframes[0]
    for i in range(1, len(stocks_indexes_dataframes_columns)):
        reunited_dataframe = reunited_dataframe.merge(right=stocks_indexes_dataframes[i], how='left',
                                                      left_on=stocks_indexes_dataframes_columns[0] + "_Date",
                                                      right_on=stocks_indexes_dataframes_columns[i] + "_Date")

    return reunited_dataframe


def link_company_with_indices_data(stock_company_dataframe: pd.DataFrame, stock_index_dataframe: pd.DataFrame) -> pd.DataFrame:
    left_stock_company_column_name = FLAGS.company_ticker_symbol + "_Date"
    right_stock_company_column_name = FLAGS.stock_indices_list[0] + "_Date"

    unified_stock_dataframe = stock_company_dataframe.merge(right=stock_index_dataframe, how='left',
                                                            left_on=left_stock_company_column_name,
                                                            right_on=right_stock_company_column_name)
    unified_stock_dataframe_with_date = unified_stock_dataframe.copy(deep=True)
    return unified_stock_dataframe_with_date


def remove_date_columns_from_unified_dataframe(unified_stock_dataframe: pd.DataFrame) -> pd.DataFrame:
    stock_company_column_name = FLAGS.company_ticker_symbol + "_Date"
    stock_indices_date_columns_names = [name + "_Date" for name in FLAGS.stock_indices_list]

    unified_date_columns = [stock_company_column_name] + stock_indices_date_columns_names
    unified_stock_dataframe.drop(columns=unified_date_columns, inplace=True)
    return unified_stock_dataframe


"""
    Returns the ending index for the dataset, such that dataset[0:index] represents
    percentage_split % of the entire dataset
"""


def compute_training_split_index(dataset: pd.DataFrame, percentage_split=80) -> int:
    number_rows = dataset.shape[0]
    return (number_rows * percentage_split) // 100


def normalize_data(unified_stock_dataframe: pd.DataFrame):
    training_ending_index = compute_training_split_index(unified_stock_dataframe,
                                                         percentage_split=FLAGS.percentage_split)

    dataset = unified_stock_dataframe.values
    dataset_mean = dataset[:training_ending_index].mean(axis=0)
    dataset_std = dataset[:training_ending_index].mean(axis=0)

    # normalized_dataset = (dataset - dataset_mean) / dataset_std
    normalized_dataset = dataset
    return normalized_dataset


def plot_company_close_price(unified_stock_dataframe_with_date: pd.DataFrame, normalized_dataset):
    plt.figure(figsize=(18, 9))
    plt.plot(range(normalized_dataset.shape[0]), normalized_dataset[:, 3])
    plt.xticks(range(0, normalized_dataset.shape[0], 500),
               unified_stock_dataframe_with_date[FLAGS.company_ticker_symbol + '_Date'].loc[::500], rotation=45)
    plt.xlabel('Date', fontsize=18)
    plt.ylabel('Close Price Normalized', fontsize=18)

    filename_path = FLAGS.output_directory + "/" + "company_close_price.png"
    plt.savefig(fname=filename_path)


def plot_train_history(history, title):
    loss = history.history['loss']
    val_loss = history.history['val_loss']

    epochs = range(len(loss))

    plt.figure()

    plt.plot(epochs, loss, 'b', label='Training loss')
    plt.plot(epochs, val_loss, 'r', label='Validation loss')
    plt.title(title)
    plt.legend()

    filename_path = FLAGS.output_directory + "/" + "train_validation_loss.png"
    plt.savefig(filename_path)


def create_time_steps(length):
    return list(range(-length, 0))


"""
    The function plots for a taken sample history-prediction-expected_output:
    -a figure containing the history line and then a set of dots for expected output and actual prediction (optional)
"""


def multi_step_plot(past_values, expected_future, prediction, title_string, figure_name):
    plt.figure(figsize=(18, 9))

    input_indices = create_time_steps(len(past_values))
    output_indices = [-1] + list(range(len(expected_future)))
    new_expected_future = np.concatenate([np.array([np.array(past_values[-1])]), np.array(expected_future)])
    new_prediction = np.concatenate([np.array([np.array(past_values[-1])]), np.array(prediction)])

    plt.plot(input_indices, np.array(past_values), label='History')
    plt.plot(output_indices, np.array(new_expected_future), 'b:',
             label='Expected Future')
    if prediction.any():
        plt.plot(output_indices, np.array(new_prediction), 'r:',
                 label='Predicted Future')
    plt.legend(loc='upper left')
    plt.title(title_string)

    filename_path = FLAGS.output_directory + "/" + figure_name + ".png"
    plt.savefig(filename_path)


"""
    Returns a tuple from two arrays:
    - first array contains the input for the network:
        -an array of the past_history size containing the considered features
    - second array contains the "sample output" of the network for comparison:
        -an array of size equal to "future" size 
"""


def multivariate_data(initial_dataset, output_target_dataset,
                      start_index, end_index,
                      past_history_size, output_target_size):
    input_data = []
    output_data = []

    start_index = start_index + past_history_size
    if end_index is None:
        end_index = len(initial_dataset) - output_target_size

    for i in range(start_index, end_index):
        indices = range(i - past_history_size, i)
        input_data.append(initial_dataset[indices])
        output_data.append(output_target_dataset[i: i + output_target_size])

    return np.array(input_data), np.array(output_data)


def mean_squared_error_loss(y_actual, y_pred):
    return tf.reduce_mean(tf.square(tf.subtract(y_actual, y_pred)))


def model_training(normalized_dataset):
    output_target_dataset = normalized_dataset[:, 3]  # it represents the 'Close' column
    training_ending_index = compute_training_split_index(normalized_dataset,
                                                         percentage_split=FLAGS.percentage_split)

    x_train, y_train = multivariate_data(normalized_dataset,
                                         output_target_dataset,
                                         0,
                                         training_ending_index,
                                         FLAGS.past_history_no_days,
                                         FLAGS.future_prediction_no_days)

    x_validation, y_validation = multivariate_data(normalized_dataset,
                                                   output_target_dataset,
                                                   training_ending_index,
                                                   None,
                                                   FLAGS.past_history_no_days,
                                                   FLAGS.future_prediction_no_days)

    buffer_size = 1000
    train_data = tf.data.Dataset.from_tensor_slices((x_train, y_train))
    train_data = train_data.cache().shuffle(buffer_size).batch(FLAGS.batch_size).repeat()

    validation_data = tf.data.Dataset.from_tensor_slices((x_validation, y_validation))
    validation_data = validation_data.shuffle(buffer_size).batch(FLAGS.batch_size)

    multi_step_model = tf.keras.models.Sequential()
    multi_step_model.add(tf.keras.layers.LSTM(256,
                                              input_shape=x_train.shape[-2:]))
                                              # return_sequences=True))
    # multi_step_model.add(tf.keras.layers.LSTM(128))
    # multi_step_model.add(tf.keras.layers.Dense(64))
    multi_step_model.add(tf.keras.layers.Dense(FLAGS.future_prediction_no_days))

    multi_step_model.compile(optimizer=tf.keras.optimizers.Adam(),
                             loss=mean_squared_error_loss,
                             metrics=[tf.keras.metrics.MeanSquaredError(),
                                      tf.keras.metrics.MeanAbsoluteError()])

    no_samples_per_epoch = math.ceil(len(x_train)/FLAGS.batch_size)
    multi_step_history = multi_step_model.fit(train_data,
                                              epochs=FLAGS.no_epochs,
                                              steps_per_epoch=no_samples_per_epoch,
                                              validation_data=validation_data,
                                              validation_steps=None,
                                              callbacks=[tf.keras.callbacks.ModelCheckpoint(
                                                  filepath=FLAGS.checkpoints_directory + "/model_{epoch}",
                                                  monitor='val_loss',
                                                  save_best_only=True,
                                                  save_weights_only=True,
                                                  verbose=1
                                              )])
    plot_train_history(multi_step_history, 'Multi-Step Training and Validation loss')

    best_checkpoint = tf.train.latest_checkpoint(FLAGS.checkpoints_directory)
    multi_step_model.load_weights(best_checkpoint)

    i = 1
    for x, y in validation_data.take(5):
        multi_step_plot(x[0][:, 3], y[0], multi_step_model.predict(x)[0], "Validation", "Validation_" + str(i))
        i += 1

    i = 1
    for x, y in train_data.take(5):
        multi_step_plot(x[0][:, 3], y[0], multi_step_model.predict(x)[0], "Train", "Train_" + str(i))
        i += 1


def create_preliminary_directories():
    if not os.path.exists(FLAGS.output_directory):
        os.mkdir(FLAGS.output_directory)
    if not os.path.exists(FLAGS.checkpoints_directory):
        os.mkdir(FLAGS.checkpoints_directory)


def main(_argv):
    unified_stock_dataframe = None
    unified_stock_dataframe_with_date = None
    create_preliminary_directories()

    company_ticker_symbol = FLAGS.company_ticker_symbol
    stock_company_dataframe = prepare_company_stock_data(company_ticker_symbol)

    if FLAGS.use_stock_indices:
        stock_index_dataframe = preprocess_stock_indexes()
        unified_stock_dataframe = link_company_with_indices_data(stock_company_dataframe, stock_index_dataframe)
        unified_stock_dataframe_with_date = unified_stock_dataframe.copy(deep=True)
        unified_stock_dataframe = remove_date_columns_from_unified_dataframe(unified_stock_dataframe)
    else:
        unified_stock_dataframe = stock_company_dataframe
        unified_stock_dataframe_with_date = unified_stock_dataframe.copy(deep=True)
        unified_stock_dataframe = remove_date_columns_from_unified_dataframe(unified_stock_dataframe)

    normalized_dataset = normalize_data(unified_stock_dataframe)
    plot_company_close_price(unified_stock_dataframe_with_date, normalized_dataset)

    model_training(normalized_dataset)


if __name__ == "__main__":
    try:
        app.run(main)
    except SystemExit:
        pass
