# -*- coding: utf-8 -*-
import re

from collections import defaultdict, Iterable
from math import ceil

from bson import ObjectId
from flask import abort
from pymongo import ASCENDING, DESCENDING, GEO2D
from pymongo.collection import Collection as BaseCollection
from pymongo.connection import Connection as BaseConnection
from pymongo.cursor import Cursor as BaseCursor

__all__ = ['PyMongo', 'Model', 'Query', 'Index', 'Cursor', 'Pagination']

_indices = defaultdict(list)


def _underscorify(name):
    name = re.sub("([A-Z]+)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return "%ss" % name.lower()


class PyMongo(object):
    """This class is used to control the pymongo integration with a Flask
    application. There are two usage modes which are similar.

    The first usage mode is to bind the instance to a specific application::

        app = Flask(__name__)
        db = PyMongo(app)

    The second usage mode is to initialize the extension and provide an
    application object later::

        db = PyMongo()

        def create_app():
          app = Flask(__name__)
          db.init_app(app)
          return app

    The latter of course has the benefit of avoiding all kinds of problems as
    described in the Flask documentation on the :ref:`~app-factories` pattern.

    During initialization, PyMongo takes another optional parameter `database`
    that can be used to set a the name of the default database to be used for
    all models that do not provide a `database` attribute themselves. This is
    often useful as one database is all that is used in many applications.

    This class also provides access to the pymongo constants for indexing and
    profiling.
    """

    def __init__(self, app=None, database=None, **kwargs):
        self.database = database
        self.Model = Model
        self.Model.query = self
        self.Query = Query
        self.Index = Index

        self._include_constants()

        if app is not None:
            self.init_app(app, **kwargs)
        else:
            self.app = None
            self.hosts = None
    
    def init_app(self, app, **kwargs):
        """Initializes `app`, a :class:`~flask.Flask` application, for use with
        the specified configuration variables. Keyword arguments passed to this
        override the configuration options.
        """
        options = {
            'max_pool_size': app.config.get('MONGO_MAX_POOL_SIZE', 10),
            'network_timeout': app.config.get('MONGO_NETWORK_TIMEOUT', None),
            'tz_aware': app.config.get('MONGO_TZ_AWARE', False),
            'slave_okay': app.config.get('MONGO_SLAVE_OKAY', False),
            'safe': app.config.get('MONGO_GETLASTERROR', False),
            'fsync': app.config.get('MONGO_GETLASTERROR_FSYNC', None),
            'j': app.config.get('MONGO_GETLASTERROR_J', None),
            'w': app.config.get('MONGO_GETLASTERROR_W', None),
            'wtimeout': app.config.get('MONGO_GETLASTERROR_W_TIMEOUT', None),
            'replicaset': app.config.get('MONGO_REPLICA_SET', None),
        }.update(kwargs)

        self.app = app
        self.hosts = app.config.get('MONGO_HOSTS', "mongodb://localhost:27017")
        self.connection = BaseConnection(self.hosts, options)

        @app.teardown_request
        def free_sockets(response):
            # release thread connection to pool so socket is reclaimed
            self.connection.end_request()
            return response

        for model, indices in _indices.iteritems():
            for index in indices:
                index.ensure(model.query)

    def _include_constants(self):
        self.ASCENDING = ASCENDING
        self.DESCENDING = DESCENDING
        self.GEO2D = GEO2D

    def __repr__(self):
        return "<%s connection=%s>" % (self.__class__.__name__, self.hosts)


class AttrDict(dict):

    def __init__(self, iterable=None, **kwargs):
        if iterable is not None:
            for key, value in iterable:
                self.__setitem__(key, value)

        for key, value in kwargs.iteritems():
            self.__setitem__(key, value)

        dict.__init__(self)

    def __getattr__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError as e:
            raise AttributeError(e)

    def __setattr__(self, key, value):
        try:
            self.__setitem__(key, value)
        except KeyError as e:
            raise AttributeError(e)

    def __delattr__(self, key):
        try:
            dict.__delitem__(self, key)
        except KeyError as e:
            raise AttributeError(e)

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            value = AttrDict(**value)
        dict.__setitem__(self, key, value)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.items())

class Query(BaseCollection):
    """The default query object used for :class:`Model`. This can be 
    subclassed and replaced for individual models by setting the
    :attr:`Model.query_class` attribute. This is a subclass of a standard
    pymongo :class:`~pymongo.collection.Collection` class and has all the
    methods of a standard collection as well.
    """

    def __init__(self, *args, **kwargs):
        self.as_class = kwargs.pop('as_class')
        BaseCollection.__init__(self, *args, **kwargs)

    def find(self, *args, **kwargs):
        """Like :meth:`~pymongo.collection.Collection.find` but sets the
        `as_class` attribute to the class of the calling model and returns a
        :class:`Cursor` instead of the traditional
        :class:`pymongo.cursor.Cursor`.
        """
        kwargs['as_class'] = self.as_class
        if not 'slave_okay' in kwargs and self.slave_okay:
            kwargs['slave_okay'] = True
        return Cursor(self, *args, **kwargs)
    
    def find_one(self, spec_or_id=None, *args, **kwargs):
        """Like :meth:`~pymongo.collection.Collection.find_one` but sets the
        `as_class` attribute to the class of the calling model and spec_or_id
        can optionally be a string.
        """
        if isinstance(spec_or_id, basestring):
            spec_or_id = ObjectId(spec_or_id)
        kwargs['as_class'] = self.as_class
        return BaseCollection.find_one(self, *args, **kwargs)

    def find_one_or_404(self, *args, **kwargs):
        """Like :meth:`find_one` but aborts with 404 if not found instead of
        returning `None`.
        """
        rv = self.find_one(*args, **kwargs)
        if rv is None:
            abort(404)
        return rv

class _QueryProperty(object):

    def __init__(self, manager, model, query_class, database, collection):
        self.manager = manager
        self.model = model
        self.query_class = query_class
        self.database = database
        self.collection = collection
        self.query = None

    def __get__(self, obj, cls):
        if self.query is None:
            if self.database is not None:
                database = self.manager.connection[self.database]
            else:
                database = self.manager.connection[self.manager.database]
            self.query = self.query_class(database, self.collection,
                                          as_class=self.model)
            del self.manager
            del self.model
            del self.query_class
            del self.database
            del self.collection
        return self.query


class ModelBase(type):

    def __new__(cls, name, bases, attrs):

        parents = [base for base in bases if isinstance(base, ModelBase)]

        if not parents:
            return type.__new__(cls, name, bases, attrs)

        database = attrs.pop('database', None)
        collection = attrs.pop('collection', None)
        indices = attrs.pop('index', None)
        query_class = attrs.pop('query_class', Query)

        # create the model without the temporary
        rv = type.__new__(cls, name, bases, attrs)

        if collection is None:
            collection = _underscorify(name)

        # collect specified indices to apply during application initialization
        if indices is not None:

            if not isinstance(indices, Iterable):
                indices = (indices,)
            
            for index in indices:
                assert isinstance(index, Index), "A flask.ext.pymongo.Index " \
                    "object is required for indices to be ensured."
                _indices[rv].append(index)

        # create the property now even if no connection exists
        rv.query = _QueryProperty(manager=rv.query, model=rv,
                                  query_class=query_class, database=database,
                                  collection=collection)

        return rv

class Model(AttrDict):
    """The base class for user-defined models."""

    __metaclass__ = ModelBase

    #: The name of the database the collection belongs to. If **None**, the
    #: database name is inferred from the :attr:`PyMongo.database` attribute.
    #: This attribute will be removed after class creation but can be accessed
    #: through the :attr:`query.database`.
    database = None

    #: The name of the collection the model represents. If **None**, the
    #: collection name is inferred from the name of the class. This attribute
    #: will be removed after class creation but can be accessed through the
    #: :attr:`query.name`.
    collection = None

    #: This is an individual or iterable of :class:`Index` to be ensured for
    #: the associated collection. This attribute will be removed after class
    #: creation and subsequently indices are ensured.
    index = None

    #: This is an instance of the class specified by :attr:`query_class` and
    #: is used to interact with the collection.
    query = None

    #: The :attr:`query` attribute is an instance of this class. By default,
    #: this is a :class:`Query`. This attribute will be removed after class
    #: creation.
    query_class = Query

    @property
    def id(self):
        """Returns the hex encoded version of `_id` instead of type
        :class:`bson.objectid.ObjectId`.
        """
        rv = self.get('_id')
        return rv and str(rv)

    def remove(self, *args, **kwargs):
        """Like :meth:`~pymongo.collection.Collection.remove` but sets the
        `spec_or_object_id` argument to the `_id` of the model instance.
        """
        return self.query.remove(self.__getitem__('_id'), *args, **kwargs)

    def save(self, *args, **kwargs):
        """Like :meth:`~pymongo.collection.Collection.save` but sets the
        `to_save` argument to the model instance.
        """
        return self.query.save(self, *args, **kwargs)

    def __repr__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join("%s=%r" % (k, v) for k, v in self.iteritems())
        )


class Index(object):
    """A wrapper around :meth:`~pymongo.collection.Collection.ensure_index` to
    enable delayed execution.
    """

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def ensure(self, collection):
        """Applies the pending arguments for
        :meth:`~pymongo.collection.Collection.ensure_index` on the given
        `collection`.
        """
        return collection.ensure_index(*self._args, **self._kwargs)

    def __repr__(self):
        return "<%s key_or_list=%s>" % (self.__class__.__name__, self._args)


class Cursor(BaseCursor):
    """The cursor object returned by :meth:`Query.find`. This cursor functions
    similarily to the native pymongo cursor but adds helpers methods for
    adding to the initial :attr:`spec` and pagination.
    """

    def filter(self, **kwargs):
        """Performs a simple dictionary update on the `spec` with
        :attr:`kwargs`. This is useful for when you want to modify the `spec`
        of the cursor returned from a query before the database is actually
        hit.
        """
        self.__spec.update(kwargs)
        return self

    def paginate(self, page, per_page=20, error_out=True):
        """Returns `per_page` items from page `page`. By default it will abort
        with 404 if no items were found and the page was larger than 1. This
        behavor can be disabled by setting `error_out` to `False`.

        Returns a :class:`Pagination` object.
        """
        if error_out and page < 1:
            abort(404)

        items = self.limit(per_page).skip((page - 1) * per_page)

        if not items and page != 1 and error_out:
            abort(404)

        return Pagination(self, page, per_page, self.count(), items)

class Pagination(object):
    """Internal helper class returned by :meth:`Cursor.paginate`. You can also
    construct it from any other pymongo cursor object if you are working
    with other libraries. It is also possible to pass `None` as query object.
    In either case, :meth:`prev` and :meth:`next` will no longer work.
    """

    def __init__(self, cursor, page, per_page, total, items):
        #: The :class:`Cursor` object used to create this pagination object.
        self.cursor = cursor
        #: The current page number (1-based).
        self.page = page
        #: The number of items to be displayed per page.
        self.per_page = per_page
        #: The total number of items matching the query.
        self.total = total
        #: The items for the current page.
        self.items = items

    @property
    def pages(self):
        """The total number of pages."""
        return int(ceil(self.total / float(self.per_page)))

    @property
    def next_num(self):
        """The next page number (1-based)."""
        return self.page + 1

    @property
    def has_next(self):
        """`True` if a next page exists."""
        return self.page < self.pages

    def next(self, error_out=False):
        """Returns a :class:`Pagination` object for the next page."""
        assert isinstance(self.cursor, Cursor), "A flask.ext.pymongo.Cursor " \
            "object is required for this method to work."
        return self.cursor.paginate(self.page + 1, self.per_page, error_out)

    @property
    def prev_num(self):
        """The previous page number (1-based)."""
        return self.page - 1

    @property
    def has_prev(self):
        """`True` if a previous page exists."""
        return self.page > 1

    def prev(self, error_out=False):
        """Returns a :class:`Pagination` object for the previous page."""
        assert isinstance(self.cursor, Cursor), "A flask.ext.pymongo.Cursor " \
            "object is required for this method to work."
        return self.cursor.paginate(self.page - 1, self.per_page, error_out)