import typing

from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from gomatic.gocd.artifacts import Config, FetchArtifact, fetch_artifact_src_from
from gomatic.gocd.artifacts import fetch_properties_from
from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import Ensurance

Command = typing.List[str]


def Task(element: ET.Element):
    runif = runif_from(element)
    if element.tag == "exec":
        command_and_args = [element.attrib["command"]] + [
            e.text for e in element.findall("arg") if e.text is not None
        ]
        working_dir = element.attrib.get(
            "workingdir", None
        )  # TODO not ideal to return "None" for working_dir
        return ExecTask(command_and_args, working_dir, runif)
    if element.tag == "fetchartifact":
        dest = element.attrib.get("dest", None)
        origin = element.attrib.get("origin", None)
        artifact_origin = element.attrib.get("artifactOrigin", None)
        artifact_id = element.attrib.get("artifactId", None)
        if artifact_origin == "external":
            return FetchArtifactTask(
                element.attrib["pipeline"],
                element.attrib["stage"],
                element.attrib["job"],
                None,
                None,
                runif,
                origin,
                artifact_origin,
                artifact_id,
                fetch_properties_from(element),
            )
        return FetchArtifactTask(
            element.attrib["pipeline"],
            element.attrib["stage"],
            element.attrib["job"],
            fetch_artifact_src_from(element),
            dest,
            runif,
            origin,
            artifact_origin,
        )
    if element.tag == "rake":
        return RakeTask(element.attrib["target"])
    raise RuntimeError("Don't know task type %s" % element.tag)


class AbstractTask(CommonEqualityMixin):
    def __init__(self, runif: str):
        self._runif = runif
        valid_values = ["passed", "failed", "any"]
        if runif not in valid_values:
            raise RuntimeError(
                'Cannot create task with runif="%s" - it must be one of %s'
                % (runif, valid_values)
            )

    @property
    def runif(self):
        return self._runif


class FetchArtifactTask(AbstractTask):
    def __init__(
        self,
        pipeline: str,
        stage: str,
        job: str,
        src: FetchArtifact = None,
        dest: str = None,
        runif="passed",
        origin: str = None,
        artifactOrigin: str = None,
        id: str = None,
        config: Config = None,
    ):
        super().__init__(runif)
        self.__pipeline = pipeline
        self.__stage = stage
        self.__job = job
        self.__src = src
        self.__dest = dest
        self.__origin = origin
        self.__artifact_origin = artifactOrigin
        self.__artifact_id = id
        if config is None:
            config = {}
        self.__config = config

    def __repr__(self):
        dest_parameter = ""
        if self.__dest is not None:
            dest_parameter = ', dest="%s"' % self.__dest

        runif_parameter = ""
        if self._runif != "passed":
            runif_parameter = ', runif="%s"' % self._runif

        origin_parameter = ""
        if self.__origin is not None:
            origin_parameter = ', origin="%s"' % self.__origin

        artifact_origin_parameter = ""
        if self.__artifact_origin is not None:
            artifact_origin_parameter = ', artifactOrigin="%s"' % self.__artifact_origin

        if self.__artifact_origin == "external":
            return (
                (
                    'FetchArtifactTask("%s", "%s", "%s", id="%s", config=%s'
                    % (
                        self.__pipeline,
                        self.__stage,
                        self.__job,
                        self.__artifact_id,
                        self.__config,
                    )
                )
                + dest_parameter
                + runif_parameter
                + origin_parameter
                + artifact_origin_parameter
                + ")"
            )

        return (
            (
                'FetchArtifactTask("%s", "%s", "%s", %s'
                % (self.__pipeline, self.__stage, self.__job, self.__src)
            )
            + dest_parameter
            + runif_parameter
            + origin_parameter
            + artifact_origin_parameter
            + ")"
        )

    type = "fetchartifact"

    @property
    def pipeline(self):
        return self.__pipeline

    @property
    def stage(self):
        return self.__stage

    @property
    def job(self):
        return self.__job

    @property
    def src(self):
        return self.__src

    @property
    def dest(self):
        return self.__dest

    @property
    def origin(self):
        return self.__origin

    @property
    def artifact_origin(self):
        return self.__artifact_origin

    @property
    def artifact_id(self):
        return self.__artifact_id

    @property
    def config(self):
        return self.__config

    def append_to(self, element: ET.Element):
        dest_parameter = ""
        if self.__dest is not None:
            dest_parameter = ' dest="%s"' % self.__dest

        origin_parameter = ""
        if self.__origin is not None:
            origin_parameter = ' origin="%s"' % self.__origin

        artifact_origin_parameter = ""
        if self.__artifact_origin is not None:
            artifact_origin_parameter = ' artifactOrigin="%s"' % self.__artifact_origin

        if self.__artifact_origin == "external":
            properties_xml = "".join(
                [
                    "<property><key>{}</key><value>{}</value></property>".format(
                        k, str(v or "")
                    )
                    for k, v in self.__config.items()
                ]
            )
            fetch_artifact_xml = """<fetchartifact pipeline="{}" stage="{}" job="{}" artifactId="{}" artifactOrigin="{}"><configuration>{}</configuration></fetchartifact>"""
            new_element = ET.fromstring(
                fetch_artifact_xml.format(
                    self.__pipeline,
                    self.__stage,
                    self.__job,
                    self.__artifact_id,
                    self.__artifact_origin,
                    properties_xml,
                )
            )
        else:
            assert self.src is not None
            src_type, src_value = self.src.as_xml_type_and_value
            new_element = ET.fromstring(
                (
                    '<fetchartifact pipeline="%s" stage="%s" job="%s" %s="%s"'
                    % (self.__pipeline, self.__stage, self.__job, src_type, src_value)
                )
                + dest_parameter
                + origin_parameter
                + artifact_origin_parameter
                + "/>"
            )

        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)


class ExecTask(AbstractTask):
    def __init__(
        self, command_and_args: Command, working_dir: str = None, runif="passed"
    ):
        super().__init__(runif)
        self.__command_and_args = command_and_args
        self.__working_dir = working_dir

    def __repr__(self):
        working_dir_parameter = ""
        if self.__working_dir is not None:
            working_dir_parameter = ', working_dir="%s"' % self.__working_dir

        runif_parameter = ""
        if self._runif != "passed":
            runif_parameter = ', runif="%s"' % self._runif

        return (
            ("ExecTask(%s" % self.command_and_args)
            + working_dir_parameter
            + runif_parameter
            + ")"
        )

    type = "exec"

    @property
    def command_and_args(self):
        return self.__command_and_args

    @property
    def working_dir(self):
        return self.__working_dir

    def append_to(self, element):
        if self.__working_dir is None:
            new_element = ET.fromstring(
                '<exec command="%s"></exec>' % self.__command_and_args[0]
            )
        else:
            new_element = ET.fromstring(
                '<exec command="%s" workingdir="%s"></exec>'
                % (self.__command_and_args[0], self.__working_dir)
            )

        for arg in self.__command_and_args[1:]:
            new_element.append(ET.fromstring("<arg>%s</arg>" % escape(arg)))

        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)


class RakeTask(AbstractTask):
    def __init__(self, target, runif="passed"):
        super().__init__(runif)
        self.__target = target

    def __repr__(self):
        return f'RakeTask("{self.__target}", "{self._runif}")'

    type = "rake"

    @property
    def target(self):
        return self.__target

    def append_to(self, element):
        new_element = ET.fromstring('<rake target="%s"></rake>' % self.__target)
        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)


def runif_from(element):
    runifs = [e.attrib["status"] for e in element.findall("runif")]
    if len(runifs) == 0:
        return "passed"
    if len(runifs) == 1:
        return runifs[0]
    if len(runifs) == 2 and "passed" in runifs and "failed" in runifs:
        return "any"
    raise RuntimeError("Don't know what multiple runif values (%s) means" % runifs)
