from lxml import etree
import os

import json
import copy

import streamlit as st
import pandas as pd



class ARXML_NUMERICAL_PARAM():
  LIST_DEF_SPEC: dict = [
    { 'tag': 'SHORT-NAME' , 'key': 'short_name' },
    { 'tag': 'DESC/L-2'   , 'key': 'desc'       },
    { 'tag': 'MIN'        , 'key': 'min'        },
    { 'tag': 'MAX'        , 'key': 'max'        },
  ]
  def __init__( self, elmt_cfg, ns_cfg, elmt_def, ns_def ):
    self.elmt_cfg = elmt_cfg
    self.ns_cfg = ns_cfg
    self.elmt_def = elmt_def
    self.ns_def = ns_def
    self.dict_info = { def_spec['key']: None for def_spec in LIST_DEF_SPEC }
    self.parse()

  def parse( self ):
    for def_spec in LIST_DEF_SPEC:
      elmt = self.elmt_def.find( def_spec['tag'], self.ns_def )
      if elmt is not None:
        self.dict_info[def_spec['key']] = elmt
    print( self.dict_info )






# class ARXML_AR_PACKAGE():
#   LIST_DEF_SPEC: dict = [
#     { 'tag': 'SHORT-NAME' , 'key': 'short_name' },
#     { 'tag': 'DESC/L-2'   , 'key': 'desc'       },
#     { 'tag': 'MIN'        , 'key': 'min'        },
#     { 'tag': 'MAX'        , 'key': 'max'        },
#   ]



class ARXML_DOC():
  def __init__( self, path ):
    self.doc = etree.parse( path )
    self.elmt_root = self.doc.getroot()
    self.ns = self.elmt_root.nsmap

    dir_doc = os.path.dirname( os.path.abspath( path ) )





class ARXML_Short_Name_Path():
  def __init__( self, short_name, xml_inst ):
    self.short_name = short_name
    self.xml_inst = xml_inst
    self.children = []
    self.parent = None

  def __iadd__( self, child ):
    if isinstance( child, ARXML_Short_Name_Path ):
      self.children.append( child )
      child.parent = self
      return self
    return NotImplemented

  def repr_with_children( self, indent = '' ):
    str_repr = indent + '- ' + self.short_name
    if self.children:
      str_repr += '\n' + '\n'.join( child.repr_with_children( indent + '  ' ) for child in self.children )
    return str_repr

  def __repr__( self ):
    return self.repr_with_children()

  def absolute_path( self ):
    if self.parent != None:
      return self.parent.absolute_path() + '/' + self.short_name
    else:
      return '/' + self.short_name

  def find( self, str_short_name_path ):
    list_short_name = str_short_name_path.split( '/', 1 )
    if not list_short_name[0]:
      list_short_name = list_short_name[1].split( '/', 1 )

    if self.short_name == list_short_name[0]:
      list_short_name.pop( 0 )
      if list_short_name:
        for child in self.children:
          short_name_path = child.find( list_short_name[0] )
          if short_name_path:
            return child.find( list_short_name[0] )
      else:
        return self
    return None

  def on_expander_change( self, path ):
    st.session_state.selectd = path

  def expender_key( self ):
    if self.parent != None:
      return self.parent.expender_key() + '_' + self.short_name
    else:
      return self.short_name

  def display_expender( self ):
    with st.expander( '{}'.format( self.short_name ), type = 'compact', key = self.expender_key(), on_change = self.on_expander_change, args = ( self.absolute_path(), ) ):
      for child in self.children:
        child.display_expender()

  def display_desc( self, spec ):
    # print( self.xml_inst.path_desc_ref )
    short_name_path_ref = spec.root.find( self.xml_inst.path_desc_ref )
    if short_name_path_ref:
      short_name_path_ref.xml_inst.display_desc()

    self.xml_inst.display_param( spec )

class ARXML_Container():
  def __init__( self, elmt, namespaces ):
    self.elmt = elmt
    self.namespaces = namespaces
    self.list_container = []
    self.short_name_path = None
    self.path_desc_ref = None
    self.path_desc = { 'desc': None, 'lower-multiplicity': None, 'upper-multiplicity': None }

  def __repr__( self ):
    if self.short_name_path is not None:
      return repr( self.short_name_path )
    return ''

  def parse( self, short_name_path_base ):
    elmt_short_name = self.elmt.find( 'SHORT-NAME', self.namespaces )
    if elmt_short_name is not None:
      self.short_name_path = ARXML_Short_Name_Path( elmt_short_name.text, self )
      short_name_path_base += self.short_name_path

    list_elmt = self.elmt.findall( 'SUB-CONTAINERS/ECUC-CONTAINER-VALUE', self.namespaces )
    for elmt in list_elmt:
      container = ARXML_Container( elmt, self.namespaces )
      container.parse( self.short_name_path )
      self.list_container.append( container )

    list_elmt = self.elmt.findall( 'SUB-CONTAINERS/ECUC-PARAM-CONF-CONTAINER-DEF', self.namespaces )
    for elmt in list_elmt:
      container = ARXML_Container( elmt, self.namespaces )
      container.parse( self.short_name_path )
      self.list_container.append( container )

    elmt = self.elmt.find( 'DEFINITION-REF', self.namespaces )
    if elmt is not None:
      self.path_desc_ref = elmt.text

    elmt = self.elmt.find( 'DESC/L-2', self.namespaces )
    if elmt is not None:
      self.path_desc['desc'] = elmt.text

  def display_desc( self ):
    with st.expander( 'DEFINITION-REF : ' + self.short_name_path.absolute_path(), expanded = False ):
      elmt_disp = copy.deepcopy( self.elmt )
      elmt_sub = elmt_disp.find( 'SUB-CONTAINERS', self.namespaces )
      if elmt_sub is not None:
        elmt_disp.remove( elmt_sub )
      # elmt_sub = elmt_disp.find( 'PARAMETERS', self.namespaces )
      # if elmt_sub is not None:
      #   elmt_disp.remove( elmt_sub )
      etree.indent( elmt_disp, space = '  ' )
      st.code( etree.tostring( elmt_disp, encoding = 'unicode' ), language = 'xml' )

  def display_param( self, spec ):
    with st.expander( 'PARAMETER-VALUES', expanded = True ):
      elmt_disp = copy.deepcopy( self.elmt )
      elmt_params = elmt_disp.find( 'PARAMETER-VALUES', self.namespaces )
      if elmt_params is not None:
        etree.indent( elmt_params, space = '  ' )
        st.code( etree.tostring( elmt_params, encoding = 'unicode' ), language = 'xml' )

        for elmt_param in elmt_params.iterfind( 'ECUC-NUMERICAL-PARAM-VALUE', self.namespaces ):
          elmt_def_ref = elmt_param.find( 'DEFINITION-REF', self.namespaces )
          if elmt_def_ref is not None:
            print( elmt_def_ref.text )
            short_name_path_ref = spec.root.find( elmt_def_ref.text )
            if short_name_path_ref is not None:
              print( 'min : {}'.format( short_name_path_ref.xml_inst.elmt.find( 'MIN', self.namespaces ).text ) )
              print( 'max : {}'.format( short_name_path_ref.xml_inst.elmt.find( 'MAX', self.namespaces ).text ) )
      else:
        st.write( 'no data' )


class ARXML_Module_Config():
  def __init__( self, elmt, namespaces ):
    self.elmt = elmt
    self.namespaces = namespaces
    self.list_container = []
    self.short_name_path = None
    self.path_desc_ref = None
    self.path_desc = { 'desc': None, 'lower-multiplicity': None, 'upper-multiplicity': None }

  def __repr__( self ):
    if self.short_name_path is not None:
      return repr( self.short_name_path )
    return ''

  def parse( self, short_name_path_base ):
    elmt_short_name = self.elmt.find( 'SHORT-NAME', self.namespaces )
    if elmt_short_name is not None:
      self.short_name_path = ARXML_Short_Name_Path( elmt_short_name.text, self )
      short_name_path_base += self.short_name_path

    list_elmt = self.elmt.findall( 'CONTAINERS/ECUC-CONTAINER-VALUE', self.namespaces )
    for elmt in list_elmt:
      container = ARXML_Container( elmt, self.namespaces )
      container.parse( self.short_name_path )
      self.list_container.append( container )

    list_elmt = self.elmt.findall( 'CONTAINERS/ECUC-PARAM-CONF-CONTAINER-DEF', self.namespaces )
    for elmt in list_elmt:
      container = ARXML_Container( elmt, self.namespaces )
      container.parse( self.short_name_path )
      self.list_container.append( container )

    elmt = self.elmt.find( 'DEFINITION-REF', self.namespaces )
    if elmt is not None:
      self.path_desc_ref = elmt.text

    elmt = self.elmt.find( 'DESC/L-2', self.namespaces )
    if elmt is not None:
      self.path_desc['desc'] = elmt.text

  def display_desc( self ):
    st.write( self.path_desc['desc'] )

  def display_param( self, spec ):
    st.write( self.path_desc['desc'] )

class ARXML_AR_Package():
  def __init__( self, elmt, namespaces ):
    self.elmt = elmt
    self.namespaces = namespaces
    self.list_module_config = []
    self.short_name_path = None

  def __repr__( self ):
    if self.short_name_path is not None:
      return repr( self.short_name_path )
    return ''

  def parse( self ):
    elmt_short_name = self.elmt.find( 'SHORT-NAME', self.namespaces )
    if elmt_short_name is not None:
      self.short_name_path = ARXML_Short_Name_Path( elmt_short_name.text, self )

    list_elmt = self.elmt.findall( 'ELEMENTS/ECUC-MODULE-CONFIGURATION-VALUES', self.namespaces )
    for elmt in list_elmt:
      module_config = ARXML_Module_Config( elmt, self.namespaces )
      module_config.parse( self.short_name_path )
      self.list_module_config.append( module_config )

    list_elmt = self.elmt.findall( 'ELEMENTS/ECUC-MODULE-DEF', self.namespaces )
    for elmt in list_elmt:
      module_config = ARXML_Module_Config( elmt, self.namespaces )
      module_config.parse( self.short_name_path )
      self.list_module_config.append( module_config )

  def find( self, str_short_name_path ):
    if self.short_name_path:
      return self.short_name_path.find( str_short_name_path )
    return None

class ARXML_Root():
  def __init__( self, elmt, namespaces ):
    self.elmt = elmt
    self.namespaces = namespaces
    self.list_ar_package = []

  def __repr__( self ):
    return '\n'.join( repr( ar_package ) for ar_package in self.list_ar_package )

  def parse( self ):
    list_elmt = self.elmt.findall( 'AR-PACKAGES/AR-PACKAGE', self.namespaces )
    for elmt in list_elmt:
      ar_package = ARXML_AR_Package( elmt, self.namespaces )
      ar_package.parse()
      self.list_ar_package.append( ar_package )

  def find( self, str_short_name_path ):
    for ar_package in self.list_ar_package:
      short_name_path = ar_package.find( str_short_name_path )
      if short_name_path:
        return short_name_path
    return None

class ARXML():
  def __init__( self, path_doc ):
    self.doc = etree.parse( path_doc )
    self.elmt_root = self.doc.getroot()
    self.namespaces = self.elmt_root.nsmap

    self.dir_doc = os.path.dirname( os.path.abspath( path_doc ) )

  def validate_with_schema( self ):
    if self.namespaces is None:
      return { 'result': False, 'commment': 'Error: No namespaces found in the root element.' }
    elif 'xsi' not in self.namespaces:
      return { 'result': False, 'commment': 'Error: No \'xsi\' namespaces found in the root element.' }

    attr_schema = self.elmt_root.get( '{{{}}}schemaLocation'.format( self.namespaces['xsi'] ) )
    if not attr_schema:
      return { 'result': False, 'commment': 'Error: No \'xsi:schemaLocation\' attribute found in the root element.' }

    arr_str_schema = attr_schema.split()
    if len( arr_str_schema ) < 2:
      return { 'result': False, 'commment': 'Error: xsi:schemaLocation format is invalid. Expected \'namespace file.xsd\'' }

    str_xsd_file = arr_str_schema[1]
    path_xsd = os.path.join( self.dir_doc, str_xsd_file )
    if not os.path.exists( path_xsd ):
      return { 'result': False, 'commment': 'Error: The schema file referenced was not found at: {}'.format( path_xsd ) }

    try:
      with open( path_xsd, 'rb' ) as file_schema:
        schema = etree.XMLSchema( etree.XML( file_schema.read() ) )
        schema.assertValid( self.doc )
        return { 'result': True, 'commment': 'Success: XML is valid based on its internal xsi:schemaLocation!' }
    except etree.XMLSyntaxError as e:
      return { 'result': False, 'commment': 'Malformed XML: {}'.format( e ) }
    except etree.DocumentInvalid as e:
      return { 'result': False, 'commment': 'Validation Failed: {}'.format( e ) }

  def parse( self ):
    self.root = ARXML_Root( self.elmt_root, self.namespaces )
    self.root.parse()

  def print( self, str_short_name_path ):
    short_name_path = self.root.find( str_short_name_path )
    print( short_name_path )

  def display_expender( self, str_short_name_path ):
    short_name_path = self.root.find( str_short_name_path )
    if short_name_path:
      short_name_path.display_expender()

  def display_desc( self, spec, str_short_name_path ):
    short_name_path = self.root.find( str_short_name_path )
    if short_name_path:
      short_name_path.display_desc( spec )



str_arxml_config_spec = 'AUTRON_AUTOSAR_Dcm_ECU_Configuration_PDF.arxml'

if 'arxml_config_spec' not in st.session_state:
  str_arxml_config_spec = 'AUTRON_AUTOSAR_Dcm_ECU_Configuration_PDF.arxml'
  st.session_state.arxml_config_spec = ARXML( str_arxml_config_spec )
  ret = st.session_state.arxml_config_spec.validate_with_schema()
  # print( '{} : {}'.format( str_arxml_config_spec, ret['commment'] ) )
  st.session_state.arxml_config_spec.parse()
if 'arxml_config' not in st.session_state:
  str_arxml_config = 'Ecud_Dcm.arxml'
  st.session_state.arxml_config = ARXML( str_arxml_config )
  ret = st.session_state.arxml_config.validate_with_schema()
  print( '{} : {}'.format( str_arxml_config, ret['commment'] ) )
  st.session_state.arxml_config.parse()
if 'selectd' not in st.session_state:
  st.session_state.selectd = None


st.markdown(
  """
  <style>
  [data-testid="stVerticalBlock"] {
    gap: 0px !important;
  }

  [data-testid="stElementContainer"] {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    margin-top: 0rem !important;
    margin-bottom: 0rem !important;
  }

  [data-testid="stExpanderDetails"] {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    margin-top: 0rem !important;
    margin-bottom: 0rem !important;
    padding-left: 1rem;
  }

  button[kind="tertiary"] {
    padding-top: 2px !important;
    padding-bottom: 2px !important;
    min-height: unset !important;
  }

  </style>
  """,
  unsafe_allow_html=True
)

st.set_page_config( page_title = 'ARXML(AUTOSAR XML) Editor', layout = 'wide' )

[ view_left, view_right ] = st.columns( [2, 8], width = 'stretch' )

with view_left:
  with st.container( border = True, height = 800 ):
    st.session_state.arxml_config.display_expender( 'AUTOSAR/Dcm' )

with view_right:
  with st.container( border = True, height = 800 ):
    if st.session_state.selectd:
      st.session_state.arxml_config.display_desc( st.session_state.arxml_config_spec, st.session_state.selectd )

# arxml.print( 'AUTOSAR/Dcm/DcmConfigSet/DcmDsd' )
# arxml.print( 'AUTOSAR/Dcm/DcmConfigSet/DcmDsl' )
# arxml.print( 'AUTOSAR/Dcm/DcmConfigSet/DcmDsp' )

