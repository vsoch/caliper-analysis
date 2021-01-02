# Caliper TensorFlow

In this analysis, we want to start with baseline examples derived for specific
versions of Tensorflow (e.g., 0.11 vs v1 and v2) and then iteratively change
the versions until we either 1) cannot build the container anymore, or 2)
can build the container, but cannot run it, or 3) can build and run it,
but produce a different result.

All examples are derived from [aymericdamien/TensorFlow-Examples](https://github.com/aymericdamien/TensorFlow-Examples)
and [this branch](https://github.com/aymericdamien/TensorFlow-Examples/tree/0.11) under an MIT LICENSE.

## Examples

 - [tensorflow_v1](tensorflow_v1)
 - [tensorflow_v11](tensorflow_v0.11)
 - **tensorflow_v2** needs conversion from notebook to scripts!

For each of the above, to ensure some reproducibility and headless-ness across runs I modified the file to:

 - set a seed for each of numpy and tensorflow
 - remove matplotlib plots and print out model information instead
 - for some long running models, decreasing training epochs or similar
 - removed any GPU usage, replacing with CPU (I don't have GPU)

## Usage

Caliper is currently intended for Python packages, as we are going to use a PypiManager.
You can first create a virtual environment just for doing the analysis (the analysis
itself will be done within containers built on the fly).

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

You then want to run the analysis with [run_analysis.py](run_analysis.py) and target
the [caliper.yaml](caliper.yaml) file that includes the libraries to use for the
install grid and functions to test.

```python
python run_analysis.py --config caliper.yaml
```

This is going to save output to a hidden `.caliper` directory (also in this present
working directory) that will have a json dump of tensorflow versions matched to dockerfiles
that can build them, and then test results (output, error, and return code) for each.

### caliper.yml

The caliper.yml file is a small configuration file to run caliper. Currently, it's fairly simply
and we need to define the dependency to run tests over (e.g., tensorflow), the Dockerfile template,
a name, and then a list of runs:

```yaml
analysis:
  name: Testing tensorflow
  dockerfile: Dockerfile
  dependency: tensorflow
  tests:
    - tensorflow_v0.11/5_MultiGPU/multigpu_basics.py
    - tensorflow_v0.11/1_Introduction/basic_operations.py
    - tensorflow_v0.11/1_Introduction/helloworld.py
    - tensorflow_v0.11/4_Utils/tensorboard_advanced.py
```

An additional test to just import the library is added by default, so if you don't define
any tests, this will be the only one run. If you want to add custom arguments for your template (beyond a base image that
is derived for your Python software, and the dependency name to derive wheels to install)
you can do this with args:

```yaml
analysis:
  name: Testing tensorflow
  dockerfile: Dockerfile
  args:
     additionaldeps: 
       - scikit-learn
```

The functionality of your arguments is up to you. In the example above, `additionaldeps`
would be a list, so likely you would loop over it in your Dockerfile template (which uses jinja2).


### Dockerfile

The [Dockerfile](Dockerfile) template (specified in the caliper.yaml) should expect
the following arguments from the caliper analysis script:

 - **base**: The base python image, derived from the wheel we need to install
 - **filename**: the url filename of the wheel to download with wget
 - **basename**: the basename of that to install with pip

Additional arguments under args will be handed to the template, and are up to you
to define and render appropriately.
