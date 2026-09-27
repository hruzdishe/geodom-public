import type { ReactNode } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

export function Reveal({
  children,
  className,
  delay=0,
  amount=.16
}:{
  children:ReactNode
  className?:string
  delay?:number
  amount?:number
}) {
  const reduceMotion = useReducedMotion()
  return <motion.div
    className={className}
    initial={reduceMotion ? false : { opacity:0,y:18 }}
    whileInView={reduceMotion ? undefined : { opacity:1,y:0 }}
    viewport={{ once:true,amount }}
    transition={{ duration:.48,delay,ease:[.22,1,.36,1] }}
  >
    {children}
  </motion.div>
}

export function Stagger({
  children,
  className
}:{
  children:ReactNode
  className?:string
}) {
  const reduceMotion = useReducedMotion()
  return <motion.div
    className={className}
    initial={reduceMotion ? false : 'hidden'}
    whileInView={reduceMotion ? undefined : 'show'}
    viewport={{ once:true,amount:.12 }}
    variants={{
      hidden:{},
      show:{ transition:{ staggerChildren:.065 } }
    }}
  >
    {children}
  </motion.div>
}

export function StaggerItem({
  children,
  className
}:{
  children:ReactNode
  className?:string
}) {
  const reduceMotion = useReducedMotion()
  return <motion.div
    className={className}
    variants={reduceMotion ? undefined : {
      hidden:{ opacity:0,y:16,scale:.985 },
      show:{ opacity:1,y:0,scale:1,transition:{ duration:.42,ease:[.22,1,.36,1] } }
    }}
  >
    {children}
  </motion.div>
}


export function PageTransition({ children }:{ children:ReactNode }) {
  const reduceMotion = useReducedMotion()
  return <motion.div
    initial={reduceMotion ? false : { opacity:0,y:8 }}
    animate={{ opacity:1,y:0 }}
    transition={{ duration:.34,ease:[.22,1,.36,1] }}
  >
    {children}
  </motion.div>
}
