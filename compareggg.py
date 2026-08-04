from lxml import etree
import os

import json
import copy

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
    if self.parent == None:
      return '/' + self.short_name
    else:
      return self.parent.absolute_path() + '/' + self.short_name

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

  def __init__( self, elmt: etree._Element, ns: dict, info, short_name_path_parent ):
    self.elmt = elmt
    self.ns = ns
    self.info = info

    self.elmts_sub = []
    self.elmts_cntr = []
    self.elmts_sub_cntr = []
    self.elmts_param = []
    self.elmts_ref = []
    self.elmts_temp = []

    self.short_name_path_parent = short_name_path_parent
    self.short_name_path = None
    self.str_desc_ref = None

    # self.init_info()
    self.to_info()

  def to_info( self ):
    if self.elmt.text:
      self.info["#text"] = self.elmt.text.strip()

    if self.elmt.attrib:
      self.info["@attributes"] = self.elmt.attrib

    str_tag = self.elmt.tag.replace( f'{{{self.ns[None]}}}', '' )
    if str_tag == 'CONTAINERS':
      elmts_child = self.elmts_cntr
    elif str_tag == 'SUB-CONTAINERS':
      elmts_child = self.elmts_sub_cntr
    elif str_tag == 'PARAMETERS':
      elmts_child = self.elmts_param
    elif str_tag == 'REFERENCES':
      elmts_child = self.elmts_ref
    else:
      elmts_child = self.elmts_temp

    short_name_path = self.short_name_path_parent
    child_short_name = self.elmt.find( 'SHORT-NAME', self.ns )
    if child_short_name is not None:
      self.short_name_path = ARXML_Short_Name_Path( child_short_name.text, self )
      if self.short_name_path_parent is not None:
        self.short_name_path_parent += self.short_name_path
      short_name_path = self.short_name_path

    child_def_ref = self.elmt.find( 'DEFINITION-REF', self.ns )
    if child_def_ref is not None:
      self.str_desc_ref = child_def_ref.text

    children = list( self.elmt )
    for child in children:
      if child.tag is etree.Comment:
        continue

      info_child = {}
      elmt_child = ARXML_ELMT( child, self.ns, info_child, short_name_path )
      self.elmts_sub.append( elmt_child )
      elmts_child.append( elmt_child )

      str_tag = child.tag.replace( f'{{{self.ns[None]}}}', '' )
      if str_tag not in self.info:
        self.info[str_tag] = info_child
      else:
        if not isinstance( self.info[str_tag], list ):
          self.info[str_tag] = [ self.info[str_tag] ]
        self.info[str_tag].append( info_child )

  def find_short_name_path_root( self ):
    if self.short_name_path is not None:
      return self.short_name_path
    else:
      for elmt_sub in self.elmts_sub:
        short_name_path = elmt_sub.find_short_name_path_root()
        if short_name_path is not None:
          return short_name_path
    return None




class ARXML_DOC():
  def __init__( self, path ):
    self.doc = etree.parse( path )
    self.elmt_root = self.doc.getroot()
    self.ns = self.elmt_root.nsmap
    self.info = dict()

    self.root = ARXML_ELMT( self.elmt_root, self.ns, self.info, None )
    self.short_name_path_root = self.root.find_short_name_path_root()
    # print( json.dumps( self.info, indent = 2 ) )
    # print( self.info )



def st_on_expander_change( short_name_path ):
  st.session_state.short_name_path_selected = short_name_path

def st_display_short_name_path_tree( short_name_path ):
  if short_name_path.short_name is None:
    for child in short_name_path.children:
      st_display_short_name_path_tree( child )
  else:
    if not short_name_path.children:
      st.button(
        short_name_path.short_name,
        type = 'tertiary',
        key = short_name_path.absolute_path().replace( '/', '_' ),
        on_click = st_on_expander_change,
        args = ( short_name_path, )
      )
    else:
      with st.expander(
          short_name_path.short_name,
          type = 'compact',
          key = short_name_path.absolute_path().replace( '/', '_' ),
          on_change = st_on_expander_change,
          args = ( short_name_path, )
        ):
        for child in short_name_path.children:
          st_display_short_name_path_tree( child )

def st_display_short_name_path_ref( short_name_path, arxml_doc_cfg_spec ):
  if short_name_path.elmt is not None:
    if short_name_path.elmt.str_desc_ref is not None:
      short_name_path_def_ref = arxml_doc_cfg_spec.short_name_path_root.find( short_name_path.elmt.str_desc_ref )
      if short_name_path_def_ref is not None:
        with st.expander( 'DEFINITION-REF : ' + short_name_path_def_ref.absolute_path(), expanded = False ):
          elmt_disp = copy.deepcopy( short_name_path_def_ref.elmt.elmt )

          elmt_sub = elmt_disp.find( 'CONTAINERS', arxml_doc_cfg_spec.ns )
          if elmt_sub is not None:
            elmt_disp.remove( elmt_sub )
          elmt_sub = elmt_disp.find( 'SUB-CONTAINERS', arxml_doc_cfg_spec.ns )
          if elmt_sub is not None:
            elmt_disp.remove( elmt_sub )
          # elmt_sub = elmt_disp.find( 'PARAMETERS', self.namespaces )
          # if elmt_sub is not None:
          #   elmt_disp.remove( elmt_sub )
          etree.indent( elmt_disp, space = '  ' )
          st.code( etree.tostring( elmt_disp, encoding = 'unicode' ), language = 'xml' )

def st_display_short_name_path_params( short_name_path, arxml_doc_cfg_spec ):
  if short_name_path.elmt is not None:
    if short_name_path.elmt.str_desc_ref is not None:
      short_name_path_def_ref = arxml_doc_cfg_spec.short_name_path_root.find( short_name_path.elmt.str_desc_ref )
      if short_name_path_def_ref is not None:
        with st.expander( short_name_path_def_ref.absolute_path() + ' - PARAMETERS', expanded = True ):
          if 'PARAMETERS' in short_name_path_def_ref.elmt.info:
            params = short_name_path_def_ref.elmt.info['PARAMETERS']
            st.json( params, expanded = 1 )
            if 'ECUC-INTEGER-PARAM-DEF' in params:
              if isinstance( params['ECUC-INTEGER-PARAM-DEF'], list ):
                for param in params['ECUC-INTEGER-PARAM-DEF']:
                  st.number_input(
                    param['SHORT-NAME']["#text"],
                    min_value = int( param['MIN']["#text"] ),
                    max_value = int( param['MAX']["#text"] ),
                    # value = int( param['DEFAULT-VALUE']["#text"], 0 ),
                    help = param['DESC']['L-2']["#text"]
                  )
              else:
                param = params['ECUC-INTEGER-PARAM-DEF']
                st.number_input(
                  param['SHORT-NAME']["#text"],
                  min_value = int( param['MIN']["#text"] ),
                  max_value = int( param['MAX']["#text"] ),
                  # value = int( param['DEFAULT-VALUE']["#text"], 0 ),
                  help = param['DESC']['L-2']["#text"]
                )
            if 'ECUC-BOOLEAN-PARAM-DEF' in params:
              if isinstance( params['ECUC-BOOLEAN-PARAM-DEF'], list ):
                for param in params['ECUC-BOOLEAN-PARAM-DEF']:
                  st.checkbox(
                    param['SHORT-NAME']["#text"],
                    # value = int( param['DEFAULT-VALUE']["#text"], 0 ),
                    help = param['DESC']['L-2']["#text"]
                  )
              else:
                param = params['ECUC-BOOLEAN-PARAM-DEF']
                st.checkbox(
                  param['SHORT-NAME']["#text"],
                  # value = int( param['DEFAULT-VALUE']["#text"], 0 ),
                  help = param['DESC']['L-2']["#text"]
                )
            if 'ECUC-FUNCTION-NAME-DEF' in params:
              if isinstance( params['ECUC-FUNCTION-NAME-DEF'], list ):
                for param in params['ECUC-FUNCTION-NAME-DEF']:
                  st.text_input(
                    param['SHORT-NAME']["#text"],
                    # value = int( param['DEFAULT-VALUE']["#text"], 0 ),
                    help = param['DESC']['L-2']["#text"]
                  )
              else:
                param = params['ECUC-FUNCTION-NAME-DEF']
                st.text_input(
                  param['SHORT-NAME']["#text"],
                  # value = int( param['DEFAULT-VALUE']["#text"], 0 ),
                  help = param['DESC']['L-2']["#text"]
                )

# st.checkbox

        with st.expander( short_name_path_def_ref.absolute_path() + ' - REFERENCES', expanded = True ):
          if 'REFERENCES' in short_name_path_def_ref.elmt.info:
            refs = short_name_path_def_ref.elmt.info['REFERENCES']
            st.json( refs, expanded = 1 )
            if 'ECUC-REFERENCE-DEF' in refs:
              if isinstance( refs['ECUC-REFERENCE-DEF'], list ):
                for ref in refs['ECUC-REFERENCE-DEF']:
                  st.button(
                    ref['SHORT-NAME']["#text"],
                    type = 'tertiary',
                    help = ref['DESC']['L-2']["#text"]
                  )
              else:
                ref = refs['ECUC-REFERENCE-DEF']
                st.button(
                  ref['SHORT-NAME']["#text"],
                  type = 'tertiary',
                  help = ref['DESC']['L-2']["#text"]
                )

        with st.expander( short_name_path_def_ref.absolute_path() + ' - SUB-CONTAINERS', expanded = True ):
          if 'SUB-CONTAINERS' in short_name_path_def_ref.elmt.info:
            st.json( short_name_path_def_ref.elmt.info['SUB-CONTAINERS'], expanded = 1 )
            # elmts_param = short_name_path_def_ref.elmt.info['PARAMETERS'].elmts_param
            # for elmt_param in elmts_param:
            #   if elmt_param.short_name_path is not None:
            #     st.write( elmt_param.short_name_path.short_name )



if 'arxml_doc_cfg_spec' not in st.session_state:
  path_arxml_cfg_spec = 'AUTRON_AUTOSAR_Dcm_ECU_Configuration_PDF.arxml'
  st.session_state.arxml_doc_cfg_spec = ARXML_DOC( path_arxml_cfg_spec )
if 'arxml_doc_cfg' not in st.session_state:
  path_arxml_cfg = 'Ecud_Dcm.arxml'
  st.session_state.arxml_doc_cfg = ARXML_DOC( path_arxml_cfg )
if 'short_name_path_selected' not in st.session_state:
  st.session_state.short_name_path_selected = None

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
    padding-left: 4px;
  }

  button[kind="tertiary"] {
    padding-top: 1px !important;
    padding-bottom: 1px !important;
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
    st_display_short_name_path_tree( st.session_state.arxml_doc_cfg.short_name_path_root )

with view_right:
  with st.container( border = True, height = 800 ):
    if st.session_state.short_name_path_selected is not None:
      st_display_short_name_path_ref( st.session_state.short_name_path_selected, st.session_state.arxml_doc_cfg_spec )
      st_display_short_name_path_params( st.session_state.short_name_path_selected, st.session_state.arxml_doc_cfg_spec )
