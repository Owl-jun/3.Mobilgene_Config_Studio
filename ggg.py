from lxml import etree
import os

import json

import streamlit as st

class ARXML_Short_Name_Path():
  def __init__( self, short_name, elmt ):
    self.short_name = short_name
    self.elmt = elmt
    self.children = []
    self.parent = None

  def __iadd__( self, child ):
    if isinstance( child, ARXML_Short_Name_Path ):
      self.children.append( child )
      child.parent = self
      return self
    return NotImplemented

  # def repr_with_children( self, indent = '' ):
  #   str_repr = indent + '- ' + self.short_name
  #   if self.children:
  #     str_repr += '\n' + '\n'.join( child.repr_with_children( indent + '  ' ) for child in self.children )
  #   return str_repr

  # def __repr__( self ):
  #   return self.repr_with_children()

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




class ARXML_DOC():
  def __init__( self, path ):
    self.doc = etree.parse( path )
    self.elmt_root = self.doc.getroot()
    self.ns = self.elmt_root.nsmap
    self.info = dict()

    self.root = ARXML_ELMT_ROOT( self.elmt_root, self.ns, self.info )
    # print( json.dumps( self.info, indent = 2 ) )
    print( self.info )




def st_display_arxml_elmt_tree( arxml_elmt ):
  if isinstance( arxml_elmt.info, dict ):
    for key, value in arxml_elmt.info.items():
      if value is not None:
        if key == 'SHORT-NAME':
          with st.expander( value['val'], type = 'compact' ):
            st.write( '111111111')

        if isinstance( value, dict ):
          if value['ref'] is not None:
            st_display_arxml_elmt_tree( value['ref'] )
          elif value['val'] is not None:
            print( key )
            print( value['val'] )
            print( '2' )
      else:
        print('hhhhhhhhh')
        print(key)
      # elif key == 'val' and value is not None:
      #   print( '1' )
        # print( value['val'] )
        # print( '2' )
        # if 'SHORT-NAME' in dict_info['val']:
        #   print('11111111')
  elif isinstance( arxml_elmt.info, list ):
    for dict_info in arxml_elmt.info:
      if dict_info['ref'] is not None:
        st_display_arxml_elmt_tree( dict_info['ref'] )

      # if dict_info['val'] is not None:

      # if key == 'val':
      #   with st.expander( arxml_elmt.info['SHORT-NAME'], type = 'compact' ):
      #     st.write( '111111111')
      # else isinstance( value, dict )






if 'arxml_doc_cfg_spec' not in st.session_state:
  path_arxml_cfg_spec = 'AUTRON_AUTOSAR_Dcm_ECU_Configuration_PDF.arxml'
  st.session_state.arxml_doc_cfg_spec = ARXML_DOC( path_arxml_cfg_spec )
if 'arxml_doc_cfg' not in st.session_state:
  path_arxml_cfg = 'Ecud_Dcm.arxml'
  # st.session_state.arxml_doc_cfg = ARXML_DOC( path_arxml_cfg )
if 'tree_selectd_path' not in st.session_state:
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
    st_display_arxml_elmt_tree( st.session_state.arxml_doc_cfg_spec.root )

with view_right:
  with st.container( border = True, height = 800 ):
    st.write( '11111' )