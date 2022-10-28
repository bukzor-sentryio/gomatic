from __future__ import annotations

from typing import Dict, Union
from xml.etree import ElementTree as ET

from gomatic.mixins import CommonEqualityMixin

Config = Dict[str, str]
FetchArtifact = Union["FetchArtifactFile", "FetchArtifactDir"]


def fetch_artifact_src_from(element: ET.Element) -> FetchArtifact:
    if "srcfile" in element.attrib:
        return FetchArtifactFile(element.attrib["srcfile"])
    if "srcdir" in element.attrib:
        return FetchArtifactDir(element.attrib["srcdir"])
    raise RuntimeError(
        "Expected srcfile or srcdir. Do not know what src type to use for "
        + ET.tostring(element, "utf-8")
    )


def fetch_properties_from(element: ET.Element) -> Union[Config, None]:
    props: dict[str, str] = {}
    for prop in element.iter("property"):
        key = prop.find("key")
        if key is None or key.text is None:
            continue
        value = prop.find("value")
        if value is None or value.text is None:
            continue
        props[key.text] = value.text
    return props if props else None


class FetchArtifactFile(CommonEqualityMixin):
    def __init__(self, src_value: str):
        self.__src_value = src_value

    def __repr__(self):
        return 'FetchArtifactFile("%s")' % self.__src_value

    @property
    def as_xml_type_and_value(self):
        return "srcfile", self.__src_value


class FetchArtifactDir(CommonEqualityMixin):
    def __init__(self, src_value: str):
        self.__src_value = src_value

    def __repr__(self):
        return 'FetchArtifactDir("%s")' % self.__src_value

    @property
    def as_xml_type_and_value(self):
        return "srcdir", self.__src_value


class Artifact(CommonEqualityMixin):
    def __init__(
        self,
        src: str = None,
        dest: str = None,
        id: str = None,
        store_id: str = None,
        config: dict[str, str] = None,
        artifact_type: str = "build",
    ):
        self._src = src
        self._dest = dest
        self._artifact_id = id
        self._store_id = store_id
        if config is None:
            config = {}
        self._config = config
        self._type = artifact_type

    def __repr__(self):
        if self._artifact_id is not None:
            if self._config is None:
                return '{}("{}", "{}")'.format(
                    self.constructor,
                    self._artifact_id,
                    self._store_id,
                )
            else:
                return '{}("{}", "{}", {})'.format(
                    self.constructor,
                    self._artifact_id,
                    self._store_id,
                    self._config,
                )
        if self._dest is None:
            return f'{self.constructor}("{self._src}")'
        else:
            return f'{self.constructor}("{self._src}", "{self._dest}")'

    @property
    def constructor(self):
        if self._type == "build":
            return "BuildArtifact"
        if self._type == "test":
            return "TestArtifact"
        if self._type == "external":
            return "ExternalArtifact"
        raise RuntimeError("Unknown artifact type %s" % self._type)

    def append_to(self, element: ET.Element, gocd_18_3_and_above=False):
        if gocd_18_3_and_above:
            self._append_to_gocd_18_3_and_above(element)
        else:
            self._append_to_gocd_18_2_and_below(element)

    def _append_to_gocd_18_3_and_above(self, element: ET.Element):
        if self._artifact_id is not None:
            if self._config is None:
                element.append(
                    ET.fromstring(
                        '<artifact id="%s" storeId="%s" type="%s" />'
                        % (self._artifact_id, self._store_id, self._type)
                    )
                )
            else:
                properties_xml = "".join(
                    [
                        "<property><key>{}</key><value>{}</value></property>".format(
                            k, str(v or "")
                        )
                        for k, v in self._config.items()
                    ]
                )
                new_element = ET.fromstring(
                    '<artifact id="{}" storeId="{}" type="{}"><configuration>{}</configuration></artifact>'.format(
                        self._artifact_id, self._store_id, self._type, properties_xml
                    )
                )
                element.append(new_element)
        elif self._dest is None:
            element.append(
                ET.fromstring(f'<artifact src="{self._src}" type="{self._type}" />')
            )
        else:
            element.append(
                ET.fromstring(
                    '<artifact src="%s" dest="%s" type="%s" />'
                    % (self._src, self._dest, self._type)
                )
            )

    def _append_to_gocd_18_2_and_below(self, element: ET.Element):
        if not self._type == "build" and not self._type == "test":
            raise RuntimeError(
                "Artifact type '%s' not supported in GoCD 18.2 and below" % self._type
            )
        tag = "artifact" if self._type == "build" else "test"
        if self._dest is None:
            element.append(ET.fromstring(f'<{tag} src="{self._src}" />'))
        else:
            element.append(
                ET.fromstring(f'<{tag} src="{self._src}" dest="{self._dest}" />')
            )

    @classmethod
    def get_artifact_for(cls, element: ET.Element):
        src = element.attrib.get("src", None)
        dest = element.attrib.get("dest", None)
        id = element.attrib.get("id", None)
        store_id = element.attrib.get("storeId", None)
        artifact_type_attribute = element.attrib.get("type", "build")
        if id is not None:
            return cls(
                id=id,
                store_id=store_id,
                config=fetch_properties_from(element),
                artifact_type=artifact_type_attribute,
            )
        if artifact_type_attribute is None:
            _type = "build" if element.tag == "artifact" else "test"
            return cls(src=src, dest=dest, artifact_type=_type)
        else:
            return cls(src=src, dest=dest, artifact_type=artifact_type_attribute)

    @classmethod
    def get_build_artifact(cls, src: str, dest: str = None):
        return cls(src=src, dest=dest, artifact_type="build")

    @classmethod
    def get_test_artifact(cls, src: str, dest: str = None):
        return cls(src=src, dest=dest, artifact_type="test")

    @classmethod
    def get_external_artifact(cls, id: str, store_id: str, config: Config = None):
        return cls(id=id, store_id=store_id, config=config, artifact_type="external")


ArtifactFor = Artifact.get_artifact_for
BuildArtifact = Artifact.get_build_artifact
TestArtifact = Artifact.get_test_artifact
ExternalArtifact = Artifact.get_external_artifact
