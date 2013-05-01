"""
============
rdflib.store
============

Types of store
--------------

``Context-aware``: An RDF store capable of storing statements within contexts
is considered context-aware. Essentially, such a store is able to partition
the RDF model it represents into individual, named, and addressable
sub-graphs.

Relevant Notation3 reference regarding formulae, quoted statements, and such:
http://www.w3.org/DesignIssues/Notation3.html

``Formula-aware``: An RDF store capable of distinguishing between statements
that are asserted and statements that are quoted is considered formula-aware.

``Transaction-capable``: capable of providing transactional integrity to the
RDF operations performed on it.

------
"""

# Constants representing the state of a Store (returned by the open method)
VALID_STORE = 1
CORRUPTED_STORE = 0
NO_STORE = -1
UNKNOWN = None

from rdflib.events import Dispatcher, Event

__all__ = ['StoreCreatedEvent', 'TripleAddedEvent', 'TripleRemovedEvent',
           'NodePickler', 'Store']


class StoreCreatedEvent(Event):
    """
    This event is fired when the Store is created, it has the following
    attribute:

      - ``configuration``: string used to create the store

    """


class TripleAddedEvent(Event):
    """
    This event is fired when a triple is added, it has the following
    attributes:

      - the ``triple`` added to the graph
      - the ``context`` of the triple, if any
      - the ``graph`` to which the triple was added
    """


class TripleRemovedEvent(Event):
    """
    This event is fired when a triple is removed, it has the following
    attributes:

      - the ``triple`` removed from the graph
      - the ``context`` of the triple, if any
      - the ``graph`` from which the triple was removed
    """

from cPickle import Pickler, Unpickler, UnpicklingError
try:
    from io import BytesIO
    assert BytesIO
except ImportError:
    from cStringIO import StringIO as BytesIO


class NodePickler(object):
    def __init__(self):
        self._objects = {}
        self._ids = {}
        self._get_object = self._objects.__getitem__

    def _get_ids(self, key):
        try:
            return self._ids.get(key)
        except TypeError:
            return None

    def register(self, object, id):
        self._objects[id] = object
        self._ids[object] = id

    def loads(self, s):
        up = Unpickler(BytesIO(s))
        up.persistent_load = self._get_object
        try:
            return up.load()
        except KeyError, e:
            raise UnpicklingError("Could not find Node class for %s" % e)

    def dumps(self, obj, protocol=None, bin=None):
        src = BytesIO()
        p = Pickler(src)
        p.persistent_id = self._get_ids
        p.dump(obj)
        return src.getvalue()


class Store(object):
    # Properties
    context_aware = False
    formula_aware = False
    transaction_aware = False
    batch_unification = False

    def __init__(self, configuration=None, identifier=None):
        """
        identifier: URIRef of the Store. Defaults to CWD
        configuration: string containing infomation open can use to
        connect to datastore.
        """
        self.__node_pickler = None
        self.dispatcher = Dispatcher()
        if configuration:
            self.open(configuration)

    def __get_node_pickler(self):
        if self.__node_pickler is None:
            from rdflib.term import URIRef
            from rdflib.term import BNode
            from rdflib.term import Literal
            from rdflib.graph import Graph, QuotedGraph, GraphValue
            from rdflib.term import Variable
            from rdflib.term import Statement
            self.__node_pickler = np = NodePickler()
            np.register(self, "S")
            np.register(URIRef, "U")
            np.register(BNode, "B")
            np.register(Literal, "L")
            np.register(Graph, "G")
            np.register(QuotedGraph, "Q")
            np.register(Variable, "V")
            np.register(Statement, "s")
            np.register(GraphValue, "v")
        return self.__node_pickler
    node_pickler = property(__get_node_pickler)

    # Database management methods
    def create(self, configuration):
        self.dispatcher.dispatch(
            StoreCreatedEvent(configuration=configuration))

    def open(self, configuration, create=False):
        """
        Opens the store specified by the configuration string. If
        create is True a store will be created if it does not already
        exist. If create is False and a store does not already exist
        an exception is raised. An exception is also raised if a store
        exists, but there is insufficient permissions to open the
        store.  This should return one of:
        VALID_STORE, CORRUPTED_STORE, or NO_STORE
        """
        return UNKNOWN

    def close(self, commit_pending_transaction=False):
        """
        This closes the database connection. The commit_pending_transaction
        parameter specifies whether to commit all pending transactions before
        closing (if the store is transactional).
        """

    def destroy(self, configuration):
        """
        This destroys the instance of the store identified by the
        configuration string.
        """

    def gc(self):
        """
        Allows the store to perform any needed garbage collection
        """
        pass

    # RDF APIs
    def add(self, (subject, predicate, object), context, quoted=False):
        """
        Adds the given statement to a specific context or to the model. The
        quoted argument is interpreted by formula-aware stores to indicate
        this statement is quoted/hypothetical It should be an error to not
        specify a context and have the quoted argument be True. It should also
        be an error for the quoted argument to be True when the store is not
        formula-aware.
        """
        self.dispatcher.dispatch(
            TripleAddedEvent(
                triple=(subject, predicate, object), context=context))

    def addN(self, quads):
        """
        Adds each item in the list of statements to a specific context. The
        quoted argument is interpreted by formula-aware stores to indicate this
        statement is quoted/hypothetical. Note that the default implementation
        is a redirect to add
        """
        for s, p, o, c in quads:
            assert c is not None, \
                "Context associated with %s %s %s is None!" % (s, p, o)
            self.add((s, p, o), c)

    def remove(self, (subject, predicate, object), context=None):
        """ Remove the set of triples matching the pattern from the store """
        self.dispatcher.dispatch(
            TripleRemovedEvent(
                triple=(subject, predicate, object), context=context))

    def triples_choices(self, (subject, predicate, object_), context=None):
        """
        A variant of triples that can take a list of terms instead of a single
        term in any slot.  Stores can implement this to optimize the response
        time from the default 'fallback' implementation, which will iterate
        over each term in the list and dispatch to tripless
        """
        if isinstance(object_, list):
            assert not isinstance(
                subject, list), "object_ / subject are both lists"
            assert not isinstance(
                predicate, list), "object_ / predicate are both lists"
            if object_:
                for obj in object_:
                    for (s1, p1, o1), cg in self.triples(
                            (subject, predicate, obj), context):
                        yield (s1, p1, o1), cg
            else:
                for (s1, p1, o1), cg in self.triples(
                        (subject, predicate, None), context):
                    yield (s1, p1, o1), cg

        elif isinstance(subject, list):
            assert not isinstance(
                predicate, list), "subject / predicate are both lists"
            if subject:
                for subj in subject:
                    for (s1, p1, o1), cg in self.triples(
                            (subj, predicate, object_), context):
                        yield (s1, p1, o1), cg
            else:
                for (s1, p1, o1), cg in self.triples(
                        (None, predicate, object_), context):
                    yield (s1, p1, o1), cg

        elif isinstance(predicate, list):
            assert not isinstance(
                subject, list), "predicate / subject are both lists"
            if predicate:
                for pred in predicate:
                    for (s1, p1, o1), cg in self.triples(
                            (subject, pred, object_), context):
                        yield (s1, p1, o1), cg
            else:
                for (s1, p1, o1), cg in self.triples(
                        (subject, None, object_), context):
                    yield (s1, p1, o1), cg

    def triples(self, triple_pattern, context=None):
        """
        A generator over all the triples matching the pattern. Pattern can
        include any objects for used for comparing against nodes in the store,
        for example, REGEXTerm, URIRef, Literal, BNode, Variable, Graph,
        QuotedGraph, Date? DateRange?

        A conjunctive query can be indicated by either providing a value of
        None for the context or the identifier associated with the Conjunctive
        Graph (if it is context aware).
        """
        subject, predicate, object = triple_pattern

    # variants of triples will be done if / when optimization is needed

    def __len__(self, context=None):
        """
        Number of statements in the store. This should only account for non-
        quoted (asserted) statements if the context is not specified,
        otherwise it should return the number of statements in the formula or
        context given.
        """

    def contexts(self, triple=None):
        """
        Generator over all contexts in the graph. If triple is specified,
        a generator over all contexts the triple is in.
        """

    def query(self, query, initNs, initBindings, queryGraph, **kwargs):
        """
        If stores provide their own SPARQL implementation, override this.

        queryGraph is None, a URIRef or '__UNION__'
        If None the graph is specified in the query-string/object
        If URIRef it specifies the graph to query,
        If  '__UNION__' the union of all named graphs should be queried
        (This is used by ConjunctiveGraphs
        Values other than None obviously only makes sense for
        context-aware stores.)

        """

        raise NotImplementedError

    # Optional Namespace methods

    def bind(self, prefix, namespace):
        """ """

    def prefix(self, namespace):
        """ """

    def namespace(self, prefix):
        """ """

    def namespaces(self):
        """ """
        if False:
            yield None

    # Optional Transactional methods

    def commit(self):
        """ """

    def rollback(self):
        """ """
