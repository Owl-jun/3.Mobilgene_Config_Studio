#region INCLUDES
from lxml import etree
import os
import json
import streamlit as st
#endregion

#region FOR_DEBUG_TREE
def print_info( info, indent = '', visited = None, file = None ):
  if visited is None:
    visited = set()

  if isinstance( info, (dict, list) ):
    info_id = id( info )
    if info_id in visited:
      print( '{}<already visited: {} (id={})>'.format( indent, type( info ).__name__, info_id ), file = file )
      return
    visited.add( info_id )

  if isinstance( info, dict ):
    if 'ref' in info and 'val' in info:
      ref = info['ref']
      if ref is None:
        print( '{}ref : None'.format( indent ), file = file )
      else:
        print( '{}ref : {} (id={})'.format( indent, type( ref ).__name__, id( ref ) ), file = file )

      val = info['val']
      if isinstance( val, (dict, list) ):
        print( '{}val :'.format( indent ), file = file )
        print_info( val, indent + '  ', visited, file )
      else:
        print( '{}val : {!r}'.format( indent, val ), file = file )
    else:
      for key, value in info.items():
        print( '{}{}'.format( indent, key ), file = file )
        print_info( value, indent + '  ', visited, file )
  elif isinstance( info, list ):
    for index, value in enumerate( info ):
      print( '{}[{}]'.format( indent, index ), file = file )
      print_info( value, indent + '  ', visited, file )
  else:
    print( '{}{!r}'.format( indent, info ), file = file )


def save_info_log( path_log, list_info ):
  with open( path_log, 'w', encoding = 'utf-8' ) as file_log:
    for index, info_log in enumerate( list_info ):
      if index > 0:
        print( file = file_log )
      print( '===== {} ====='.format( info_log['name'] ), file = file_log )
      print_info( info_log['info'], file = file_log )

#endregion

#region !<<UNUSE>>! ARXML_Short_Name_Path()
# class ARXML_Short_Name_Path():
#   def __init__( self, short_name, elmt ):
#     self.short_name = short_name
#     self.elmt = elmt
#     self.children = []
#     self.parent = None

#   def __iadd__( self, child ):
#     if isinstance( child, ARXML_Short_Name_Path ):
#       self.children.append( child )
#       child.parent = self
#       return self
#     return NotImplemented
# #region
#   # def repr_with_children( self, indent = '' ):
#   #   str_repr = indent + '- ' + self.short_name
#   #   if self.children:
#   #     str_repr += '\n' + '\n'.join( child.repr_with_children( indent + '  ' ) for child in self.children )
#   #   return str_repr

#   # def __repr__( self ):
#   #   return self.repr_with_children()
# #endregion

#   def absolute_path( self ):
#     if self.parent != None:
#       return self.parent.absolute_path() + '/' + self.short_name
#     else:
#       return '/' + self.short_name

#   def find( self, str_short_name_path ):
#     list_short_name = str_short_name_path.split( '/', 1 )
#     if not list_short_name[0]:
#       list_short_name = list_short_name[1].split( '/', 1 )

#     if self.short_name == list_short_name[0]:
#       list_short_name.pop( 0 )
#       if list_short_name:
#         for child in self.children:
#           short_name_path = child.find( list_short_name[0] )
#           if short_name_path:
#             return child.find( list_short_name[0] )
#       else:
#         return self
#     return None
#endregion

#region ARXML_ELMT()
class ARXML_ELMT():
  LIST_DEF_SPEC: list = [
  ]

  def __init__( self, elmt: etree._Element, ns: dict, info ):
    self.elmt = elmt
    self.ns = ns
    self.info = info

    # self.init_info()
    self.to_info()

  def init_info( self ):
    for def_spec in self.LIST_DEF_SPEC:
      self.info[def_spec['tag']] = { 'ref': None, 'val': None }

  def to_info( self ):
    if isinstance( self.info, dict ):
      for def_spec in self.LIST_DEF_SPEC:
        self.info[def_spec['tag']] = { 'ref': None, 'val': None } 
        elmt_sub = self.elmt.find( def_spec['tag'], self.ns ) 
        if elmt_sub is not None:
          if def_spec['dict']['type'] in [list, dict]:
            self.info[def_spec['tag']]['val'] = def_spec['dict']['type']()
            if def_spec['type'] is not None:
              self.info[def_spec['tag']]['ref'] = globals()[def_spec['type']]( elmt_sub, self.ns, self.info[def_spec['tag']]['val'] )
          else:
            self.info[def_spec['tag']]['val'] = def_spec['dict']['type']( elmt_sub.text )
    else:
      for def_spec in self.LIST_DEF_SPEC:
        elmts_sub = self.elmt.findall( def_spec['tag'], self.ns )
        for elmt_sub in elmts_sub:
          info_sub = { 'ref': None, 'val': None }
          self.info.append( info_sub )
          info_sub['val'] = def_spec['dict']['type']()
          if def_spec['type'] is not None:
            info_sub['ref'] = globals()[def_spec['type']]( elmt_sub, self.ns, info_sub['val'] )
#region !<<UNUSE>>! UNUSE_FUNCTION_IN_ARXML_ELMT
  # def init_info( self ):
  #   for def_spec in self.LIST_DEF_SPEC:
  #     if def_spec['dict']['key'] is not None:
  #       if def_spec['dict']['type'] in [list, dict]:
  #         self.info[def_spec['dict']['key']] = def_spec['dict']['type']()
  #       else:
  #         self.info[def_spec['dict']['key']] = None

  # def to_info( self ):
  #   if isinstance( self.info, list ):
  #     for def_spec in self.LIST_DEF_SPEC:
  #       elmts = self.elmt.findall( def_spec['tag'], self.ns )
  #       for elmt in elmts:
  #         info = def_spec['dict']['type']()
  #         self.info.append( info )
  #         globals()[def_spec['type']]( elmt, self.ns, info )
  #   else:
  #     for def_spec in self.LIST_DEF_SPEC:
  #       if def_spec['dict']['type'] in [list, dict]:
  #         elmt = self.elmt.find( def_spec['tag'], self.ns )
  #         if elmt is not None:
  #           globals()[def_spec['type']]( elmt, self.ns, self.info[def_spec['dict']['key']] )
  #       else:
  #         elmt = self.elmt.find( def_spec['tag'], self.ns )
  #         if elmt is not None:
  #           if def_spec['dict']['key'] is None:
  #             aaa = ''
  #             # def_spec['type']( self.info )
  #           else:
  #             self.info[def_spec['dict']['key']] = def_spec['dict']['type']( elmt.text )
#endregion
#endregion

#region ARXML_ELMT DEFINITIONS
class ARXML_ELMT_CNTR( ARXML_ELMT ):
  LIST_DEF_SPEC: list = [
    { 'tag': 'SHORT-NAME',                        'type': None,               'dict': { 'key': 'name',  'type': str   } },
    { 'tag': 'SUB-CONTAINERS' ,                   'type': 'ARXML_ELMT_CNTRS', 'dict': { 'key': 'cntrs', 'type': list  } },
  ]

class ARXML_ELMT_CNTRS( ARXML_ELMT ):
  LIST_DEF_SPEC: list = [
    { 'tag': 'ECUC-CONTAINER-VALUE',              'type': 'ARXML_ELMT_CNTR',  'dict': { 'key': None,    'type': dict  } },
    { 'tag': 'ECUC-PARAM-CONF-CONTAINER-DEF',     'type': 'ARXML_ELMT_CNTR',  'dict': { 'key': None,    'type': dict  } },
  ]

class ARXML_ELMT_ELMT( ARXML_ELMT ):
  LIST_DEF_SPEC: list = [
    { 'tag': 'SHORT-NAME',                        'type': None,               'dict': { 'key': 'name',  'type': str   } },
    { 'tag': 'CONTAINERS',                        'type': 'ARXML_ELMT_CNTRS', 'dict': { 'key': 'cntrs', 'type': list  } },
  ]

class ARXML_ELMT_ELMTS( ARXML_ELMT ):
  LIST_DEF_SPEC: list = [
    { 'tag': 'ECUC-MODULE-CONFIGURATION-VALUES',  'type': 'ARXML_ELMT_ELMT',  'dict': { 'key': None,    'type': dict  } },
    { 'tag': 'ECUC-MODULE-DEF',                   'type': 'ARXML_ELMT_ELMT',  'dict': { 'key': None,    'type': dict  } },
  ]

class ARXML_ELMT_PKG( ARXML_ELMT ):
  LIST_DEF_SPEC: list = [
    { 'tag': 'SHORT-NAME',                        'type': None,               'dict': { 'key': 'name',  'type': str   } },
    { 'tag': 'ELEMENTS',                          'type': 'ARXML_ELMT_ELMTS', 'dict': { 'key': 'elmts', 'type': list  } },
  ]

class ARXML_ELMT_PKGS( ARXML_ELMT ):
  LIST_DEF_SPEC: list = [
    { 'tag': 'AR-PACKAGE',                        'type': 'ARXML_ELMT_PKG',   'dict': { 'key': None,    'type': dict  } },
  ]

class ARXML_ELMT_ROOT( ARXML_ELMT ):
  LIST_DEF_SPEC: list = [
    { 'tag': 'AR-PACKAGES',                       'type': 'ARXML_ELMT_PKGS',  'dict': { 'key': 'pkgs',  'type': list  } },
  ]
#endregion

#region ARXML_DOC()
class ARXML_DOC():
  def __init__( self, path ):
    self.doc = etree.parse( path )  # get file and convert to tree
    self.elmt_root = self.doc.getroot() # get root xml tag -> output e. g. {http://autosar.org/schema/r4.0}AUTOSAR
    self.ns = self.elmt_root.nsmap  # save {namespace(ns)} info
    self.info = dict()

    self.root = ARXML_ELMT_ROOT( self.elmt_root, self.ns, self.info )
#endregion

#region Util Functions
def get_arxml_elmt_short_name( arxml_elmt ):
  if not isinstance( arxml_elmt.info, dict ):
    return None

  info_short_name = arxml_elmt.info.get( 'SHORT-NAME' )
  if not isinstance( info_short_name, dict ):
    return None

  return info_short_name['val']


def iter_arxml_elmt_children( arxml_elmt ):
  if isinstance( arxml_elmt.info, dict ):
    for value in arxml_elmt.info.values():
      if isinstance( value, dict ) and value['ref'] is not None:
        yield value['ref']
  elif isinstance( arxml_elmt.info, list ):
    for dict_info in arxml_elmt.info:
      if dict_info['ref'] is not None:
        yield dict_info['ref']


def is_arxml_module_configuration( arxml_elmt ):
  return etree.QName( arxml_elmt.elmt ).localname == 'ECUC-MODULE-CONFIGURATION-VALUES'


def st_display_arxml_elmt_children( arxml_elmt, current_path, display_module_tree ):
  for child in iter_arxml_elmt_children( arxml_elmt ):
    st_display_arxml_elmt_tree( child, current_path, display_module_tree )


def st_display_arxml_elmt_tree( arxml_elmt, parent_path = '', display_module_tree = False ):
  short_name = get_arxml_elmt_short_name( arxml_elmt )

  if short_name is None:
    st_display_arxml_elmt_children( arxml_elmt, parent_path, display_module_tree )
    return

  current_path = parent_path + '/' + short_name
  display_module_tree = display_module_tree or is_arxml_module_configuration( arxml_elmt )

  if display_module_tree:
    with st.expander( short_name, type = 'compact', key = current_path ):
      st_display_arxml_elmt_children( arxml_elmt, current_path, display_module_tree )
  else:
    st_display_arxml_elmt_children( arxml_elmt, current_path, display_module_tree )
#endregion


path_arxml_cfg_spec = 'AUTRON_AUTOSAR_Dcm_ECU_Configuration_PDF.arxml'
path_arxml_cfg = 'Ecud_Dcm.arxml'

if 'arxml_doc_cfg_spec' not in st.session_state:
  st.session_state.arxml_doc_cfg_spec = ARXML_DOC( path_arxml_cfg_spec )
if 'arxml_doc_cfg' not in st.session_state:
  st.session_state.arxml_doc_cfg = ARXML_DOC( path_arxml_cfg )
if 'selectd' not in st.session_state:
  st.session_state.selectd = None

#region !<<UNUSE>>! FOR_DEBUG_TREE
# path_info_log = os.path.join( os.path.dirname( os.path.abspath( __file__ ) ), 'arxml_info_log.txt' )
# save_info_log(
#   path_info_log,
#   [
#     { 'name': path_arxml_cfg_spec, 'info': st.session_state.arxml_doc_cfg_spec.info },
#     { 'name': path_arxml_cfg,      'info': st.session_state.arxml_doc_cfg.info      },
#   ]
# )
#endregion

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
    st_display_arxml_elmt_tree( st.session_state.arxml_doc_cfg.root )

with view_right:
  with st.container( border = True, height = 800 ):
    st.write( '11111' )
